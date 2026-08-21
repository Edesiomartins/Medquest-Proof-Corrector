"""Escalonamento de leituras duvidosas: TTA e consenso entre modelos.

Itens 12 e 8 do docs/HTR_PLANO_EXECUCAO.md, reunidos aqui porque são a mesma
mecânica com fontes de variação diferentes:

- **TTA (item 12)** — reenviar o *mesmo* recorte preparado de outro jeito.
  Modelos de visão são surpreendentemente sensíveis ao *rendering*: o mesmo traço
  em 2× de escala, ou sem normalização nenhuma, costuma ser lido corretamente
  quando a primeira tentativa falhou.
- **Consenso (item 8)** — mandar a *mesma* imagem para uma família de modelo
  diferente. Erros de famílias diferentes tendem a não coincidir.

O que os dois produzem, além de uma leitura melhor, é a coisa que o sistema não
tinha: **uma confiança que significa algo**. A autoavaliação do modelo é
notoriamente mal calibrada — ele reporta "alta" ao alucinar texto em caixa vazia.
A concordância entre leituras independentes, medida em CER, é ancorada em
evidência: se três leituras do mesmo traço convergem, elas provavelmente estão
certas; se divergem, o traço é genuinamente ambíguo e a questão precisa de gente.

Custo
-----
Cada escalonamento é uma chamada extra. O projeto opera sob restrição explícita
de custo, então nada disto roda por padrão: só entra quando a primeira leitura
declara confiança **baixa**, e com teto de tentativas. Numa prova em que o modelo
lê bem, o custo é exatamente o de antes.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from app.services.vision.htr_metrics import character_error_rate, normalize_text
from app.services.vision.ink import normalize_for_reading
from app.services.vision.lines import restack_lines

logger = logging.getLogger(__name__)

# CER entre duas leituras abaixo do qual elas são consideradas concordantes.
AGREEMENT_CER = 0.10
# Acima disto as leituras discordam a ponto de não haver o que votar: é caso de
# gente olhar, com as hipóteses lado a lado.
DISAGREEMENT_CER = 0.30


@dataclass
class Hypothesis:
    text: str
    source: str
    """De onde veio: `original`, `upscale_2x`, `sem_normalizacao`, ou o modelo."""
    reported_confidence: str = "baixa"


@dataclass
class Consensus:
    text: str
    confidence: str
    """`alta` / `media` / `baixa`, derivada da concordância — não do autorrelato."""
    agreement_cer: float
    """CER médio entre as hipóteses. 0 = leituras idênticas."""
    hypotheses: list[Hypothesis] = field(default_factory=list)
    needs_human: bool = False
    reason: str = ""

    @property
    def alternatives(self) -> list[str]:
        """Leituras distintas da escolhida, para oferecer ao revisor."""
        chosen = normalize_text(self.text)
        seen: list[str] = []
        for item in self.hypotheses:
            if normalize_text(item.text) != chosen and item.text not in seen:
                seen.append(item.text)
        return seen


# --- variantes de imagem (TTA) ------------------------------------------------


def build_tta_variants(crop_path: str, output_dir: Path, limit: int = 2) -> list[tuple[str, str]]:
    """Gera preparos alternativos do mesmo recorte. Retorna [(nome, caminho)].

    A ordem é deliberada — a variante mais provável de resolver vem primeiro,
    porque `limit` corta o resto e cada corte economiza uma chamada:

    1. `upscale_2x` — resolução é a causa nº 1 das falhas; dobrar a escala com
       Lanczos é o que mais costuma resolver.
    2. `sem_normalizacao` — a normalização não pode ser caminho sem volta. Se ela
       apagou um traço fraco, o original ainda o tem.
    3. `linhas_separadas` — desfaz a sobreposição entre linhas vizinhas, que faz
       o modelo pular linha em bloco denso.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    source = Path(crop_path)
    variants: list[tuple[str, str]] = []

    try:
        with Image.open(source) as opened:
            image = opened.convert("RGB")
    except Exception as exc:  # noqa: BLE001 — recorte ilegível não derruba a leitura
        logger.warning("Não foi possível abrir %s para TTA: %s", source, exc)
        return []

    builders: list[tuple[str, Callable[[], Image.Image]]] = [
        ("upscale_2x", lambda: image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)),
        ("sem_normalizacao", lambda: normalize_for_reading(image, clahe_clip=1.0)),
        ("linhas_separadas", lambda: restack_lines(image)),
    ]

    for name, build in builders[: max(0, limit)]:
        try:
            variant = build()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Variante TTA %s falhou: %s", name, exc)
            continue
        if variant.size == image.size and name == "linhas_separadas":
            # `restack_lines` devolve a original quando não há o que separar;
            # reenviar imagem idêntica gastaria uma chamada por nada.
            continue
        path = output_dir / f"{source.stem}__{name}.png"
        variant.save(path, format="PNG", optimize=True)
        variants.append((name, str(path)))

    return variants


# --- votação ------------------------------------------------------------------


def _mean_cer_to_others(index: int, texts: list[str]) -> float:
    others = [text for position, text in enumerate(texts) if position != index]
    if not others:
        return 0.0
    return sum(character_error_rate(other, texts[index]) for other in others) / len(others)


def pick_consensus(hypotheses: list[Hypothesis]) -> Consensus:
    """Escolhe a leitura mais central e mede a concordância.

    A escolha é o **medoide**: a hipótese com menor CER médio contra as demais.
    Votar palavra a palavra (ROVER) daria um resultado marginalmente melhor ao
    custo de alinhamento; o medoide tem a vantagem de nunca inventar um texto que
    nenhum modelo produziu — o que importa quando o resultado vira nota.

    Empate resolve pela ordem de chegada, que é a ordem de qualidade esperada:
    a leitura original vem primeiro.
    """
    usable = [item for item in hypotheses if normalize_text(item.text)]
    if not usable:
        return Consensus(
            text="",
            confidence="alta",
            agreement_cer=0.0,
            hypotheses=hypotheses,
            needs_human=False,
            reason="Todas as leituras vieram vazias; caixa provavelmente sem resposta.",
        )

    if len(usable) == 1:
        return Consensus(
            text=usable[0].text,
            confidence=usable[0].reported_confidence,
            agreement_cer=0.0,
            hypotheses=hypotheses,
            needs_human=usable[0].reported_confidence == "baixa",
            reason="Leitura única; sem segunda opinião para comparar.",
        )

    texts = [item.text for item in usable]
    scores = [_mean_cer_to_others(index, texts) for index in range(len(texts))]
    best = min(range(len(texts)), key=lambda index: scores[index])
    agreement = sum(scores) / len(scores)

    if agreement < AGREEMENT_CER:
        confidence, needs_human = "alta", False
        reason = f"{len(usable)} leituras independentes convergiram (CER médio {agreement:.3f})."
    elif agreement < DISAGREEMENT_CER:
        confidence, needs_human = "media", True
        reason = f"Leituras divergem em partes (CER médio {agreement:.3f}); conferir."
    else:
        confidence, needs_human = "baixa", True
        reason = (
            f"Leituras discordam demais (CER médio {agreement:.3f}); "
            "traço ambíguo, decidir olhando o recorte."
        )

    return Consensus(
        text=usable[best].text,
        confidence=confidence,
        agreement_cer=agreement,
        hypotheses=hypotheses,
        needs_human=needs_human,
        reason=reason,
    )


def should_escalate(reading_confidence: str, *, enabled: bool) -> bool:
    """Só escala leitura declarada como baixa, e só se o escalonamento estiver ligado.

    Escalar por padrão multiplicaria o custo de toda prova para melhorar as poucas
    questões que precisam.
    """
    return bool(enabled) and str(reading_confidence or "").lower() == "baixa"
