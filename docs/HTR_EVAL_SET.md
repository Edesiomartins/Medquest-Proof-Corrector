# Conjunto de avaliação de HTR — como montar

Este é o item 3 do [plano de HTR](HTR_PLANO_EXECUCAO.md), e é a peça que falta
para que as melhorias de leitura deixem de ser hipótese. O código do arnês já
está pronto (`backend/scripts/eval_htr.py`); o que ele precisa é de dados.

## Por que isso não é opcional

Todas as mudanças feitas no pipeline — recorte por caixa, novo
pré-processamento, detector de tinta, alinhamento — são fundamentadas, e algumas
têm medição própria (o QR saiu de 22% de falha para ~0%; o alinhamento recupera o
recorte de uma foto torta). Mas **"o sistema lê cursiva melhor" continua sem
medição**. Sem um conjunto de referência não há como saber:

- se a mudança ajudou de fato, e quanto;
- se ela ajudou no caso comum e piorou um bolsão (lápis fraco, cursiva ligada);
- se a confiança reportada tem qualquer relação com o erro real — e portanto se
  o gate de revisão manual significa alguma coisa.

## O que coletar

Cerca de **200 recortes** de provas reais já corrigidas. Nem todos precisam ser
difíceis: um conjunto só de casos difíceis mede outra coisa.

Inclua de propósito:

- **caixas em branco** (~15% do conjunto). São elas que medem alucinação, o erro
  mais grave do sistema: nota atribuída a resposta que não existe.
- **respostas curtas** ("não sei", "actina e miosina"), que quebravam a heurística
  antiga de fallback por contagem de palavras.
- **rasuras, setas de inserção e continuação com asterisco**, que o prompt agora
  instrui a tratar.
- **abreviações médicas** (HAS, DM2, IAM, ICC).

## Formato

Um diretório com os PNGs e um `labels.jsonl`, uma linha por recorte:

```json
{"crop": "p001_q01.png", "reference": "o deslizamento dos filamentos de actina e miosina", "strata": ["cursiva_ligada", "caneta_azul", "scanner"]}
{"crop": "p001_q03.png", "reference": "", "strata": ["vazia", "scanner"]}
```

`reference` é a transcrição feita **à mão**, exatamente como o aluno escreveu:

- não corrija português nem ortografia;
- não complete palavras;
- preserve abreviações como escritas;
- **omita** texto que o aluno riscou (ele apagou aquilo);
- use `[ilegível]` só quando for realmente impossível ler.

A regra é: a referência é o que está no papel, não o que o aluno quis dizer. Se a
referência for "melhorada", o número medido fica melhor que a realidade e o
conjunto perde a utilidade.

## Estratificação

Marque cada recorte com os eixos abaixo. As falhas de HTR se concentram em
bolsões e **a média global esconde qual** — o relatório quebra as métricas por
estrato justamente por isso.

| Eixo | Valores |
|---|---|
| Escrita | `cursiva_ligada` · `bastao` · `mista` |
| Instrumento | `lapis` · `caneta_azul` · `caneta_preta` |
| Captura | `scanner` · `celular` |
| Conteúdo | `vazia` · `curta` · `com_rasura` |

## Rodando

```bash
cd backend

# linha de base a partir de transcrições já gravadas, sem gastar LLM
python scripts/eval_htr.py --labels eval/labels.jsonl --predictions eval/baseline.jsonl

# roda o pipeline real sobre os recortes (gasta chamadas)
python scripts/eval_htr.py --labels eval/labels.jsonl --crops eval/crops --run-model

# compara duas execuções
python scripts/eval_htr.py --labels eval/labels.jsonl \
    --predictions eval/antes.jsonl --compare eval/depois.jsonl --json eval/relatorio.json
```

## Como ler o relatório

- **CER** é a métrica principal. Ela é proporcional ao tamanho da resposta, então
  um acento errado numa frase longa pesa pouco — que é o comportamento certo,
  porque é isso que prediz o trabalho do revisor. A WER trataria um acento e uma
  palavra completamente errada como o mesmo erro.
- **alucinação em vazia** merece olhar isolado: qualquer valor acima de zero é
  nota atribuída a resposta inexistente.
- **confiança × CER** deve ser **negativa** (mais confiança, menos erro). Perto de
  zero significa que a confiança não carrega informação e o gate de revisão está
  preso a um número sem significado.

## Depois: o ciclo se fecha sozinho

Toda correção que o professor faz na tela de revisão é um par
`(recorte, transcrição do modelo, transcrição humana)` — dado rotulado de graça,
exatamente no formato deste conjunto. É o item 13 do plano: persistir esses pares
faz o conjunto de avaliação crescer sem esforço adicional e, em alguns milhares
de exemplos, viabiliza um ajuste fino do modelo de leitura.
