# Snapshot de Execução — Melhoria da Leitura de Letra Cursiva (HTR)

> **Propósito deste arquivo:** retomar o trabalho sem reanalisar o código.
> Contém o diagnóstico já feito, âncoras exatas de `arquivo:linha`, decisões
> pendentes e a ordem de execução. Ao retomar, leia SÓ este arquivo + os
> arquivos citados nos itens que for executar.
>
> Data da análise: 2026-08-21 · Branch: `main` · Commit base: `2c4cb30`

---

## 1. Mapa mental do sistema (o que já foi descoberto)

Existem **dois pipelines paralelos e divergentes**:

| Pipeline | Arquivo | Gatilho | Como lê |
|---|---|---|---|
| **Visual** (ativo p/ discursivas) | `backend/app/services/visual_exam_pipeline.py` | `POST /analyze-discursive-pdf` (`backend/app/api/v1/visual_exam_analysis.py:49`) | Página **inteira** → VLM via OpenRouter |
| **Estruturado** (Celery) | `backend/app/workers/pipeline.py` | batch de upload | Crop por manifesto + OCR API + LLM |

O pipeline **estruturado já tem** o que o **visual ignora**:

- manifesto de geometria: `backend/app/services/generator/sheet_layout.py` (`AnswerBoxPlacement`, `ManifestPage`, `fiducials_for_page`, `pdf_answer_box_to_pil_pixels`)
- persistido em `Exam.layout_manifest_json` (`backend/app/models/exam.py:15`, gravado em `backend/app/api/v1/exams.py:427`)
- QR por página: `backend/app/services/vision/qr_decode.py` (`decode_sheet_qr`)
- crop por box já implementado: `backend/app/workers/pipeline.py:510-517`

**O `visual_exam_pipeline` não usa manifesto, não usa QR, não usa fiduciais.**
Ele chama `maybe_crop_answer_regions` (detector Canny genérico) e **descarta o
resultado** — só aproveita a contagem (`visual_exam_pipeline.py:77`).

---

## 2. Achados, com âncoras exatas

### P0-A — Vazamento do gabarito no prompt de transcrição

- `visual_exam_pipeline.py:76` passa `"rubric_summary": _rubric_summary(rubric)` no contexto.
- `_compact_question` (`visual_exam_pipeline.py:385`) inclui `expected_answer`.
- `openrouter_vision_client.py:166-174` (`_build_prompt`) serializa o contexto inteiro
  no prompt; filtra apenas `vision_model` e `image_path`.

**Efeito:** o modelo lê a resposta esperada ANTES de transcrever → *priming*.
Completa palavras ilegíveis com o gabarito, infla nota e **esconde as falhas de
leitura**. Parte da sensação de "corrige bem" pode vir daqui.

**Regra a adotar:** transcrição é **cega**. Rubrica só na etapa de correção.
Se quiser ajudar, passar **léxico de termos do domínio** — nunca `expected_answer`
nem os critérios de pontuação.

### P0-B — `QUESTION_SEMANTIC_GUARDS` zera questões de outras provas

- Definição: `visual_exam_pipeline.py:20-24` — termos de fisiologia muscular
  fixos para as questões 1, 2 e 3.
- Uso: `visual_exam_pipeline.py:160` → se não bate, `score = 0.0`,
  `verdict = "incorreta"`, revisão manual obrigatória.
- `_semantic_guard_matches` (`:471`) retorna `True` só quando NÃO há guarda para
  o número — ou seja, **Q1/Q2/Q3 de qualquer prova** caem na guarda de músculo.

**Efeito:** numa prova de cardiologia, a Q1 é zerada indevidamente.
É hack de debug de uma prova específica. Ou vira config por prova, ou sai.

### P1 — Resolução efetiva é a causa nº 1 das falhas de leitura

- `pdf_page_renderer.py:12` — `dpi=220` (default usado em `visual_exam_pipeline.py:52`)
- `pdf_page_renderer.py:68` — `_resize_if_too_large(max_side=3200)`
- Página **inteira** vai ao VLM (`visual_exam_pipeline.py:71-79`)

Conta da altura-de-x da cursiva:

| | x-height papel | px @220 DPI | px após downscale do VLM |
|---|---|---|---|
| Página inteira | ~2,5 mm | ~21 px | **~8 px** |
| Crop do box @380 DPI | ~2,5 mm | ~37 px | **~37 px** |

Abaixo de ~16–20 px de x-height ninguém lê cursiva de forma confiável.
Hoje entrega-se ~8 px. **Maior ROI do projeto.**

Solução: usar `Exam.layout_manifest_json` → `pdf_answer_box_to_pil_pixels` →
`page.get_pixmap(matrix, clip=rect)` do PyMuPDF (recorta em coordenadas PDF, não
rasteriza a página toda em alta) → **1 crop por chamada**.
Efeito colateral bom: elimina risco de truncar em `max_tokens: 4096`
(`openrouter_vision_client.py:143`) e a confusão de numeração de questão.

### P1 — Pré-processamento destrói traço

`exam_image_preprocess.py:110-117` (`_normalize_contrast`):

```
grayscale → autocontrast(cutoff=1) → Contrast(1.25)
→ Sharpness(1.15) → UnsharpMask(radius=1, percent=120, threshold=3)
→ colorize("#111111","#ffffff")
```

Problemas, em ordem de gravidade:

1. **`grayscale` numa folha com caixa CINZA de resposta** (o layout desenha área
   cinza — ver `sheet_layout.py`). Caneta azul sobre cinza tem contraste
   cromático alto e de luminância baixo → o grayscale joga fora justamente o
   canal que separava tinta de fundo. Lápis e azul fraco desaparecem.
2. **`UnsharpMask` empilhado com `Sharpness`** → halo e **quebra de ligaduras
   finas**, que é a informação que define cursiva.
3. **`autocontrast` é global** → foto de celular com luz desigual satura um canto
   e estoura o outro. Contraste tem que ser **local**.
4. **`colorize`** reinjeta ruído de quantização sem benefício.

Substituto proposto (ordem importa):

```
EXIF transpose
→ estimar fundo (morphological closing kernel grande, ou median blur ~51px)
→ dividir imagem pelo fundo   ← remove sombra/iluminação de foto de celular
→ separar tinta por canal: min(R,G,B) ou a*/b* do LAB — NÃO luminância
→ CLAHE (clipLimit ~2.0, tile 8x8) no lugar do autocontrast global
→ upscale 2x Lanczos se x-height estimada < 25px
→ SEM sharpen, SEM unsharp, SEM binarização
→ salvar PNG em RGB
```

**Guardar também a imagem original** (ver item TTA) — a normalização não pode
ser caminho sem volta.

### P1 — `align_scan_page` é stub

`backend/app/services/vision/page_align.py:20` → `return page_image, True, None`
(retorna sucesso **sempre**).

Consequência: toda a lógica de `alignment_failed` em
`workers/pipeline.py:470-545` existe e **nunca dispara**.

`fiducials_for_page()` (`sheet_layout.py:~93`) já posiciona 4 marcadores nos
cantos e eles vão no manifesto. Detectar + `cv2.getPerspectiveTransform` resolve:

- **deskew** (3° de rotação já degrada HTR de forma perceptível; 5° é fatal);
- **crops corretos** pelo manifesto em scans não perfeitos;
- **sinal de qualidade real**: reprojection error alto → página mal digitalizada,
  marcar antes de gastar chamada de LLM.

*Considerar trocar os fiduciais quadrados por marcadores **ArUco*** no gerador —
detecção muito mais robusta, `cv2.aruco` pronto.

### P1 — Não existe sinal de confiança calibrado

Hoje:

- `reading_confidence: "alta"|"media"|"baixa"` — autoavaliação do modelo
  (`openrouter_vision_client.py:38-41`, normalizado em `:296`)
- `ocr_confidence: 0.0` — float inventado pelo modelo (`:305`)

Ambos **mal calibrados**. VLM alucinando texto em box vazio reporta `"alta"`.
O gate de revisão manual está preso a um número sem significado.

Confiança de verdade, em ordem crescente de custo:

- **(a) Detector de tinta determinístico** — razão de pixels de tinta no crop após
  remoção de fundo. Abaixo do limiar → "sem resposta", **sem chamar LLM**. Mata a
  classe de erro mais constrangedora (nota em resposta inexistente) e economiza.
- **(b) Consenso entre 2 modelos** — ex. `google/gemini-2.5-flash` +
  `qwen/qwen2.5-vl-72b-instruct` (famílias diferentes). Levenshtein normalizado:
  `CER < 0,10` → aceita; `0,10–0,30` → 3º modelo, voto majoritário por alinhamento
  (ROVER); `> 0,30` → revisão humana com as hipóteses lado a lado.
- **(c) Azure Document Intelligence `prebuilt-read` como âncora** — o próprio
  `docs/OCR_STRATEGY.md` o elege para o MVP e **nunca foi implementado**
  (`vision/ocr.py` só tem Google Vision e Mistral). Devolve **confiança e bbox
  POR PALAVRA**. Arquitetura: Azure transcreve → palavras com conf ≥ 0.85 aceitas
  → palavras abaixo são recortadas e mandadas ao VLM com as vizinhas como contexto
  ("qual é esta palavra?"). O VLM vira **desambiguador pontual**, não transcritor.

Detalhe: `vision/ocr.py:112` pede `confidence_scores_granularity: "page"` ao
Mistral — descarta o sinal por palavra. Mistral OCR é OCR documental, fraco em
cursiva; não é o provedor certo para esse papel.

### P2 — `_needs_fallback` é errado para respostas curtas

`vision/ocr.py:277-283`: `len(words) < 3 → needs_fallback`.
"actina e miosina" = 3 palavras; "fibras tipo I" = 3. Box vazio = 0 palavras →
dispara fallback caro à toa. Precisa distinguir **box vazio** (densidade de tinta
~0, item (a) acima) de **leitura falhada**.

### P2 — TTA (test-time augmentation)

VLMs são muito sensíveis ao *rendering* da mesma imagem. Em baixa confiança,
reenviar o MESMO crop com preparo diferente costuma resolver:
upscale 2× Lanczos · versão **crua sem normalização** · CLAHE mais agressivo ·
inversão de polaridade. 2–3 variantes + voto.

### P2 — Segmentação por linha (respostas discursivas longas)

Bloco de 5 linhas de uma vez é pior que 5 tiras: ascendentes/descendentes de
linhas vizinhas se sobrepõem; o modelo pula linhas em blocos densos; e não dá
para localizar o erro. Perfil de projeção horizontal sobre o mapa de tinta
resolve a maioria; seam carving / A* para linhas que se tocam.
**Considerar pautar as caixas de resposta** com linhas cinza 20% no gerador —
ajuda o aluno a manter a linha de base e o algoritmo a segmentar.

### P2 — Prompt pede 5 coisas ao mesmo tempo

`openrouter_vision_client.py:19-70` (`VISION_EXTRACTION_PROMPT`) pede numa única
chamada: identidade + números de questão + enunciado detectado + transcrição +
notas + autoconfiança + JSON válido. Objetivos múltiplos degradam cada um.

Separar em:

1. **Identidade** — crop do cabeçalho + **QR** (`decode_sheet_qr` existe e o
   `visual_exam_pipeline` **nunca chama**). O QR carrega
   `MQPC|exam_id|student_id|page|total` de forma confiável; usar regex em nome
   ("aluno 003") como fonte de identidade (`_infer_student_code`,
   `openrouter_vision_client.py:325`) é frágil havendo QR na página.
2. **Transcrição** — 1 crop, 1 questão, prompt curto e **cego**, saída em texto
   puro delimitado (JSON aninhado gasta atenção que devia ir para os traços).
3. **Correção** — texto + rubrica, sem imagem.

Instruções de cursiva que faltam no prompt: rasuras (texto riscado deve ser
**omitido**, não transcrito), setas de inserção, continuação com asterisco no
verso, abreviações médicas (HAS, DM2, IAM, ICC — manter como escritas), e as
confusões dominantes em PT-BR manuscrito: `a/o`, `n/u`, `r/n`, `m/nn`, `ç/c`,
acentos ausentes.

### P2 — Tela de revisão não mostra a imagem

`frontend/src/app/review/page.tsx:371-372` exibe só
`<p>Crop ref: {s.answer_crop_path}</p>`.
`answer_crop_path` é a string `batch=…/page=…/q=…` (montada em
`workers/pipeline.py:~516`) — **o crop nem é persistido em disco**.

Corrigir 4 palavras de cursiva olhando a imagem leva 3 segundos. Sem imagem o
revisor não revisa: ele aceita. Persistir crops + mostrar
**crop à esquerda / transcrição editável à direita**, com as hipóteses
divergentes do consenso como sugestões clicáveis.

### P0 — Não há como medir nada

Sem eval set, sem CER/WER, sem baseline. Toda melhoria acima é hipótese até ser
medida — e algumas vão piorar casos não previstos.

Montar `scripts/eval_htr.py` + ~200 crops reais transcritos à mão, versionados.
Métricas: **CER** (a que importa), WER, taxa de alucinação em box vazio, taxa de
revisão manual disparada, **correlação confiança × CER real** (mede se o gate
presta), custo e latência por página.
**Estratificar** por: cursiva ligada · bastão · mista · lápis · caneta azul ·
caneta preta · scanner · foto de celular. As falhas se concentram em bolsões;
a média esconde.

**Fechar o ciclo:** toda correção do professor na tela de revisão é um par
`(crop, transcrição_modelo, transcrição_humana)` rotulado de graça. Persistir.
Em ~2–5 mil pares → LoRA no Qwen2.5-VL ou fine-tune de TrOCR
(`microsoft/trocr-base-handwritten` adaptado a PT-BR).

---

## 3. Ordem de execução

| # | Ação | Esforço | Impacto | Status |
|---|---|---|---|---|
| 1 | Remover `expected_answer` do prompt de transcrição (P0-A) | 30 min | Integridade da nota | **[x]** |
| 2 | Neutralizar `QUESTION_SEMANTIC_GUARDS` (P0-B) | 30 min | Corrige zeros indevidos | **[x]** |
| 3 | Eval set + CER (baseline) | 1 dia | Viabiliza todo o resto | [ ] |
| 4 | **Crop por manifesto, 1 questão/chamada, ~380 DPI** | 1–2 dias | **Muito alto** | [ ] |
| 5 | Pré-processamento novo (illumination + CLAHE, sem sharpen) | meio dia | Alto | [ ] |
| 6 | Detector de tinta (box vazio determinístico) | 2 h | Alto (mata alucinação) | [ ] |
| 7 | Homografia pelos fiduciais (`page_align`) | 1–2 dias | Alto | [ ] |
| 8 | Consenso 2 modelos + CER como confiança | 1 dia | Alto | [ ] |
| 9 | Crop na tela de revisão | 1 dia | Alto (percebido) | [ ] |
| 10 | Azure `prebuilt-read` como âncora + VLM desambiguador | 2–3 dias | Alto | [ ] |
| 11 | Segmentação por linha | 2 dias | Médio (discursivas longas) | [ ] |
| 12 | TTA em baixa confiança | meio dia | Médio | [ ] |
| 13 | Loop de rotulagem → fine-tune | contínuo | Alto (longo prazo) | [ ] |

**Itens 1, 2, 4, 5 e 6 sozinhos já devem mudar o patamar** — nenhum deles exige
trocar de modelo ou de fornecedor.

---

## 4. Decisões pendentes do usuário (bloqueiam itens específicos)

1. **Convergência dos dois pipelines** — o `visual_exam_pipeline` deve absorver a
   geometria do manifesto e os dois convergirem? É refatoração de verdade.
   *Bloqueia o item 4 na forma completa (dá para fazer o item 4 só no pipeline
   visual, sem unificar, se preferir escopo menor).*
2. **Entrar ou não com Azure Document Intelligence** — adiciona fornecedor e
   credencial novos. *Bloqueia o item 10.*
3. **Trocar fiduciais quadrados por ArUco no gerador** — muda o PDF gerado, logo
   provas já impressas com o layout antigo deixam de casar. *Afeta o item 7.*

---

## 5. Ao retomar

Sugestão: começar pelos **itens 1 e 2** (bugs, baixo risco, ~1 h no total) e
montar o **item 3** (harness de CER), que é o que permite provar tudo o que vier
depois. Responder às 3 decisões da seção 4 destrava o restante.

Config relevante (`backend/app/core/config.py`):

- `OPENROUTER_VISION_MODEL = "qwen/qwen2.5-vl-72b-instruct"`
- `OPENROUTER_VISION_FALLBACKS = "qwen/qwen2.5-vl-32b-instruct,qwen/qwen-2.5-vl-7b-instruct,google/gemini-2.5-flash"`
- `OCR_PROVIDER = "mistral,google_vision"` · `GOOGLE_VISION_API_KEY` · `MISTRAL_API_KEY`
- Não há `AZURE_*` — precisaria ser criado para o item 10.
