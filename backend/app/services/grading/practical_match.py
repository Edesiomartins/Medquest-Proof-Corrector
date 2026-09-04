"""Comparação determinística entre a resposta prática do aluno e o gabarito.

Prova prática pede um nome anatômico curto, escrito com as abreviações de sala
de aula ("M. Sóleo E.", "O. Calcâneo D."). A comparação acontece em três eixos
independentes, e não por semelhança da frase inteira:

- classe estrutural (osso, músculo, artéria, veia, nervo, ...);
- lateralidade (direito/esquerdo);
- núcleo, o que sobra depois de tirar as duas anteriores e as palavras vazias.

Comparar a frase inteira confunde "artéria femoral" com "nervo femoral" e
reprova "osso calcâneo do pé D." contra "O. Calcâneo D.". Separar os eixos
resolve os dois casos: o aluno pode acrescentar contexto à vontade, mas não
pode trocar a estrutura nem o lado.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

CORRECT = "correta"
PENDING = "revisao_pendente"
WRONG = "incorreta"

# Palavras que só ligam a frase e nunca identificam a estrutura.
STOPWORDS = frozenset(
    {"o", "a", "os", "as", "do", "da", "de", "dos", "das", "no", "na", "em", "ao", "aos", "e"}
)

# Forma canônica de cada classe estrutural, já sem acento e em minúsculas.
STRUCTURE_CLASSES = {
    "osso": "osso",
    "ossos": "osso",
    "musculo": "musculo",
    "musculos": "musculo",
    "arteria": "arteria",
    "arterias": "arteria",
    "veia": "veia",
    "veias": "veia",
    "nervo": "nervo",
    "nervos": "nervo",
    "ligamento": "ligamento",
    "ligamentos": "ligamento",
    "tendao": "tendao",
    "tendoes": "tendao",
}

LATERALITY_WORDS = frozenset({"esquerdo", "esquerda", "direito", "direita"})

# Siglas de uma letra só expandem quando vêm com ponto: "a." é artéria, "a"
# sozinho é artigo. Sem essa distinção, "a cabeça longa do bíceps" viraria uma
# artéria e conflitaria com o gabarito muscular.
_DOTTED_ABBREVIATIONS = {
    "m": "musculo",
    "a": "arteria",
    "v": "veia",
    "n": "nervo",
    "l": "ligamento",
    "t": "tendao",
    "o": "osso",
}

# Siglas de duas ou mais letras não são ambíguas e dispensam o ponto.
_PLAIN_ABBREVIATIONS = {
    "mm": "musculos",
    "musc": "musculo",
    "aa": "arterias",
    "vv": "veias",
    "nn": "nervos",
    "ll": "ligamentos",
    "tt": "tendoes",
    "oss": "ossos",
    "os": "osso",
}

_COMPACT_PREFIXES = sorted(
    [*_PLAIN_ABBREVIATIONS, *_DOTTED_ABBREVIATIONS], key=len, reverse=True
)


@dataclass
class MatchResult:
    status: str
    reason: str
    similarity: float = 0.0
    normalized_answer: str = ""
    expected_used: str = ""
    matched_core: list[str] = field(default_factory=list)
    missing_core: list[str] = field(default_factory=list)


def strip_accents(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFD", str(value or ""))
        if unicodedata.category(char) != "Mn"
    )


def separate_compact_anatomy_abbreviations(text: str) -> str:
    """Aceita escrita compacta comum, como M.Soleo, A.Braquial ou O.Calcaneo."""
    pattern = r"\b(" + "|".join(_COMPACT_PREFIXES) + r")\.(?=[a-z])"
    return re.sub(pattern, r"\1. ", str(text or ""))


def expand_anatomy_abbreviations(text: str) -> str:
    out = f" {separate_compact_anatomy_abbreviations(strip_accents(text).lower())} "
    for short, full in _PLAIN_ABBREVIATIONS.items():
        out = re.sub(rf"\b{short}\.?(?=\s|$)", f" {full} ", out)
    for short, full in _DOTTED_ABBREVIATIONS.items():
        out = re.sub(rf"\b{short}\.(?=\s|$)", f" {full} ", out)
    return re.sub(r"\s+", " ", out).strip()


def normalize_practical_answer(value: str) -> str:
    text = strip_accents(value).lower()
    text = separate_compact_anatomy_abbreviations(text)
    text = expand_anatomy_abbreviations(text)
    text = re.sub(r"\besq(?:\.|uerda|uerdo)?\b", " esquerdo ", text)
    text = re.sub(r"\bdir(?:\.|eita|eito)?\b", " direito ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = _normalize_trailing_laterality_token(text)
    text = _canonicalize_practical_aliases(text)
    return text


def expected_answer_variants(expected: str) -> list[str]:
    parts = re.split(r"\s*(?:;|\||/|\n|, ou | ou )\s*", expected)
    variants = [normalize_practical_answer(part) for part in parts if str(part).strip()]
    normalized_full = normalize_practical_answer(expected)
    if normalized_full and normalized_full not in variants:
        variants.append(normalized_full)
    return [item for item in variants if item]


def practical_similarity(answer_norm: str, expected_norm: str) -> float:
    """Mantida apenas como número informativo no JSON de depuração."""
    if not answer_norm or not expected_norm:
        return 0.0
    ratio = SequenceMatcher(None, answer_norm, expected_norm).ratio()
    answer_tokens = set(answer_norm.split())
    expected_tokens = set(expected_norm.split())
    overlap = len(answer_tokens & expected_tokens) / max(1, len(expected_tokens))
    return (0.65 * ratio) + (0.35 * overlap)


def match_answer(answer_raw: str, expected_raw: str) -> MatchResult:
    """Compara a resposta do aluno com cada variante aceita do gabarito."""
    answer_norm = normalize_practical_answer(answer_raw)
    variants = expected_answer_variants(expected_raw)
    if not answer_norm or not variants:
        return MatchResult(status=WRONG, reason="nao_confere", normalized_answer=answer_norm)

    results = [_match_variant(answer_norm, variant) for variant in variants]
    best = max(results, key=_result_rank)
    best.normalized_answer = answer_norm
    return best


def _match_variant(answer_norm: str, expected_norm: str) -> MatchResult:
    answer_class, answer_core = _split_axes(answer_norm)
    expected_class, expected_core = _split_axes(expected_norm)
    similarity = practical_similarity(answer_norm, expected_norm)

    matched: list[str] = []
    missing: list[str] = []
    approximate = False
    for token in expected_core:
        kind = _find_token(token, answer_core)
        if kind is None:
            missing.append(token)
            continue
        matched.append(token)
        approximate = approximate or kind == "aproximado"

    result = MatchResult(
        status=WRONG,
        reason="nao_confere",
        similarity=similarity,
        expected_used=expected_norm,
        matched_core=matched,
        missing_core=missing,
    )

    # Sem núcleo (gabarito só com estrutura e lado), os dois eixos restantes decidem.
    core_hit = bool(matched) or not expected_core

    if core_hit and not _laterality_compatible(answer_norm, expected_norm):
        result.reason = "lateralidade"
        return result
    if core_hit and expected_class and answer_class and answer_class != expected_class:
        result.reason = "estrutura"
        return result

    if missing and matched:
        result.status = PENDING
        result.reason = "nucleo_parcial"
        return result
    if missing:
        return result

    if approximate:
        result.status = PENDING
        result.reason = "leitura_aproximada"
        return result

    result.status = CORRECT
    result.reason = "confere"
    return result


_RANK = {WRONG: 0, PENDING: 1, CORRECT: 2}
# Entre respostas erradas, a razão específica explica melhor do que "não confere".
_REASON_RANK = {"nao_confere": 0, "estrutura": 1, "lateralidade": 2}


def _result_rank(result: MatchResult) -> tuple[int, int, float]:
    return (
        _RANK[result.status],
        _REASON_RANK.get(result.reason, 0),
        result.similarity,
    )


def _split_axes(normalized: str) -> tuple[str, list[str]]:
    """Separa a classe estrutural do núcleo, descartando lado e palavras vazias."""
    structure = ""
    core: list[str] = []
    for token in normalized.split():
        if token in STRUCTURE_CLASSES:
            structure = structure or STRUCTURE_CLASSES[token]
            continue
        if token in LATERALITY_WORDS or token in STOPWORDS:
            continue
        core.append(token)
    return structure, core


def _find_token(expected_token: str, answer_core: list[str]) -> str | None:
    if expected_token in answer_core:
        return "exato"
    for candidate in answer_core:
        if _is_typo_of(expected_token, candidate):
            return "aproximado"
    return None


def _is_typo_of(first: str, second: str) -> bool:
    """Tolera ruído de OCR sem aproximar termos anatômicos distintos.

    Uma letra de diferença em palavra longa é quase sempre leitura ruim
    ("bucinafor" por "bucinador"). Duas letras só valem em palavras bem longas,
    o que mantém pares como anterior/posterior e radial/medial separados.
    """
    shortest = min(len(first), len(second))
    if shortest < 6:
        return False
    distance = _edit_distance(first, second)
    return distance <= (2 if shortest >= 10 else 1)


def _edit_distance(first: str, second: str) -> int:
    if abs(len(first) - len(second)) > 2:
        return 3
    previous = list(range(len(second) + 1))
    for i, char_a in enumerate(first, start=1):
        current = [i]
        for j, char_b in enumerate(second, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (char_a != char_b),
                )
            )
        previous = current
    return previous[-1]


def _laterality_compatible(answer: str, expected: str) -> bool:
    expected_lat = extract_laterality(expected)
    if not expected_lat:
        return True
    answer_lat = extract_laterality(answer)
    if not answer_lat:
        return True
    return answer_lat == expected_lat


def extract_laterality(value: str) -> str:
    text = normalize_practical_answer(value)
    has_left = " esquerdo" in f" {text}" or " esquerda" in f" {text}"
    has_right = " direito" in f" {text}" or " direita" in f" {text}"
    if has_left and not has_right:
        return "left"
    if has_right and not has_left:
        return "right"
    return ""


def _normalize_trailing_laterality_token(text: str) -> str:
    """Mapeia apenas marcador final isolado (E/D) para lateralidade."""
    tokens = text.split()
    if not tokens:
        return ""
    tail = tokens[-1]
    if tail == "e":
        tokens[-1] = "esquerdo"
    elif tail == "d":
        tokens[-1] = "direito"
    return " ".join(tokens)


def _canonicalize_practical_aliases(text: str) -> str:
    if not text:
        return ""
    out = f" {text} "
    # Remove ruído comum de OCR que não define a estrutura.
    out = re.sub(r"\bilegivel\b", " ", out)
    # Sinônimos recorrentes nas provas práticas.
    out = re.sub(r"\bgrande dorsal\b", " latissimo do dorso ", out)
    out = re.sub(r"\banconea?\b", " anconeo ", out)
    out = re.sub(r"\bbucinator\b", " bucinador ", out)
    out = re.sub(r"\bhalix\b", " halux ", out)
    out = re.sub(r"\bvleo\b", " soleo ", out)
    return re.sub(r"\s+", " ", out).strip()
