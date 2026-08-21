"""Métricas de qualidade de transcrição manuscrita (HTR).

Item 3 do docs/HTR_PLANO_EXECUCAO.md. Sem isto, toda melhoria de leitura é
hipótese: o pipeline não tem como dizer se ficou melhor ou pior, e algumas
mudanças que ajudam no caso comum pioram casos não previstos.

**CER (Character Error Rate)** é a métrica que importa aqui, não a WER. Numa
resposta de prova, errar um acento em "contração" e errar a palavra inteira
custam a mesma WER; a CER distingue, e é a CER que prediz se o professor vai
precisar corrigir a transcrição.

Duas medidas que a CER não captura, e que valem separado:

- **Alucinação em caixa vazia.** O modelo escrever qualquer coisa onde o aluno
  não escreveu nada é o erro mais grave do sistema — vira nota atribuída a
  resposta inexistente. Uma média de CER esconde isso.
- **Calibração da confiança.** De nada adianta o gate de revisão manual se a
  confiança reportada não tem relação com o erro real. Aqui isso é medido como
  correlação de postos entre confiança e CER.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Sequence


def levenshtein(a: Sequence, b: Sequence) -> int:
    """Distância de edição. Implementação em duas linhas de tabela.

    Escrita à mão de propósito: `python-Levenshtein` e `rapidfuzz` não estão nas
    dependências, e trazer um pacote nativo para uma função de vinte linhas
    cobraria caro em portabilidade de build.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for i, item_a in enumerate(a, start=1):
        current = [i]
        for j, item_b in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,  # remoção
                    current[j - 1] + 1,  # inserção
                    previous[j - 1] + (item_a != item_b),  # substituição
                )
            )
        previous = current
    return previous[-1]


def normalize_text(text: str, *, strip_accents: bool = False, fold_case: bool = True) -> str:
    """Normalização usada antes de comparar transcrições.

    Espaço em branco é sempre colapsado: quebra de linha extra não é erro de
    leitura. Acento, por padrão, **conta** como erro — em português ele muda a
    palavra, e ignorá-lo esconderia uma falha real do modelo. `strip_accents`
    existe para medir os dois números lado a lado quando isso for útil.
    """
    text = str(text or "")
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text).strip()
    if fold_case:
        text = text.casefold()
    if strip_accents:
        text = "".join(
            char
            for char in unicodedata.normalize("NFD", text)
            if unicodedata.category(char) != "Mn"
        )
    return text


def character_error_rate(reference: str, hypothesis: str, **kwargs) -> float:
    """CER = distância de edição / tamanho da referência.

    Referência vazia com hipótese vazia é acerto perfeito (0.0). Referência vazia
    com hipótese preenchida é alucinação: devolve 1.0, não infinito.
    """
    ref = normalize_text(reference, **kwargs)
    hyp = normalize_text(hypothesis, **kwargs)
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / len(ref)


def word_error_rate(reference: str, hypothesis: str, **kwargs) -> float:
    ref = normalize_text(reference, **kwargs).split()
    hyp = normalize_text(hypothesis, **kwargs).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / len(ref)


@dataclass(frozen=True)
class Sample:
    """Um par (verdade, leitura) do conjunto de avaliação."""

    reference: str
    hypothesis: str
    confidence: str | None = None
    """`alta` / `media` / `baixa` reportada pelo sistema."""
    strata: tuple[str, ...] = ()
    """Ex.: ("cursiva_ligada", "caneta_azul", "celular"). As falhas se concentram
    em bolsões, e a média esconde: sem estratificar não se enxerga qual."""
    crop_id: str = ""


@dataclass
class Report:
    samples: int = 0
    cer: float = 0.0
    wer: float = 0.0
    cer_no_accents: float = 0.0
    empty_boxes: int = 0
    hallucinated_empty: int = 0
    hallucination_rate: float = 0.0
    missed_answers: int = 0
    perfect_reads: int = 0
    confidence_cer_correlation: float | None = None
    by_stratum: dict[str, "Report"] = field(default_factory=dict)

    def as_dict(self) -> dict:
        payload = {
            "samples": self.samples,
            "cer": round(self.cer, 4),
            "wer": round(self.wer, 4),
            "cer_no_accents": round(self.cer_no_accents, 4),
            "empty_boxes": self.empty_boxes,
            "hallucinated_empty": self.hallucinated_empty,
            "hallucination_rate": round(self.hallucination_rate, 4),
            "missed_answers": self.missed_answers,
            "perfect_reads": self.perfect_reads,
            "confidence_cer_correlation": (
                round(self.confidence_cer_correlation, 4)
                if self.confidence_cer_correlation is not None
                else None
            ),
        }
        if self.by_stratum:
            payload["by_stratum"] = {k: v.as_dict() for k, v in self.by_stratum.items()}
        return payload


_CONFIDENCE_RANK = {"baixa": 0, "media": 1, "alta": 2}


def evaluate(samples: Iterable[Sample], *, stratify: bool = True) -> Report:
    """Agrega as métricas sobre o conjunto de avaliação."""
    samples = list(samples)
    report = Report(samples=len(samples))
    if not samples:
        return report

    cers: list[float] = []
    confidences: list[int] = []
    paired_cers: list[float] = []

    for sample in samples:
        cer = character_error_rate(sample.reference, sample.hypothesis)
        cers.append(cer)
        report.wer += word_error_rate(sample.reference, sample.hypothesis)
        report.cer_no_accents += character_error_rate(
            sample.reference, sample.hypothesis, strip_accents=True
        )

        reference_empty = not normalize_text(sample.reference)
        hypothesis_empty = not normalize_text(sample.hypothesis)

        if reference_empty:
            report.empty_boxes += 1
            if not hypothesis_empty:
                report.hallucinated_empty += 1
        elif hypothesis_empty:
            report.missed_answers += 1

        if cer == 0.0 and not reference_empty:
            report.perfect_reads += 1

        rank = _CONFIDENCE_RANK.get(str(sample.confidence or "").lower())
        if rank is not None:
            confidences.append(rank)
            paired_cers.append(cer)

    count = len(samples)
    report.cer = sum(cers) / count
    report.wer /= count
    report.cer_no_accents /= count
    report.hallucination_rate = (
        report.hallucinated_empty / report.empty_boxes if report.empty_boxes else 0.0
    )
    report.confidence_cer_correlation = _spearman(confidences, paired_cers)

    if stratify:
        buckets: dict[str, list[Sample]] = {}
        for sample in samples:
            for stratum in sample.strata:
                buckets.setdefault(stratum, []).append(sample)
        report.by_stratum = {
            name: evaluate(group, stratify=False) for name, group in sorted(buckets.items())
        }

    return report


def _spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Correlação de postos entre confiança reportada e erro real.

    Espera-se **negativa**: quanto maior a confiança, menor o CER. Perto de zero
    significa que a confiança não carrega informação — e então o gate de revisão
    manual está preso a um número sem significado, que era exatamente o
    diagnóstico do plano.

    Usa postos porque a confiança é ordinal (`baixa` < `media` < `alta`), não
    numérica: a distância entre "baixa" e "media" não é conhecida.
    """
    if len(x) < 3 or len(set(x)) < 2 or len(set(y)) < 2:
        return None

    rank_x = _ranks(x)
    rank_y = _ranks(y)
    n = len(x)
    mean_x = sum(rank_x) / n
    mean_y = sum(rank_y) / n

    covariance = sum((a - mean_x) * (b - mean_y) for a, b in zip(rank_x, rank_y, strict=True))
    var_x = sum((a - mean_x) ** 2 for a in rank_x)
    var_y = sum((b - mean_y) ** 2 for b in rank_y)
    if var_x <= 0 or var_y <= 0:
        return None
    return covariance / math.sqrt(var_x * var_y)


def _ranks(values: Sequence[float]) -> list[float]:
    """Postos com média nos empates — necessário porque a confiança tem 3 níveis."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        stop = index
        while stop + 1 < len(order) and values[order[stop + 1]] == values[order[index]]:
            stop += 1
        average = (index + stop) / 2.0 + 1.0
        for position in range(index, stop + 1):
            ranks[order[position]] = average
        index = stop + 1
    return ranks
