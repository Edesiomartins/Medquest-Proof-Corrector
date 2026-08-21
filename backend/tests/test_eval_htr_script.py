"""O arnes de avaliacao (scripts/eval_htr.py) precisa ser confiavel para medir.

Se ele engolir uma linha corrompida em silencio, o relatorio mente -- e o
relatorio e a unica coisa que separa melhoria medida de melhoria imaginada.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import eval_htr  # noqa: E402


def _write(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return path


def test_reads_jsonl_ignoring_blank_lines_and_comments(tmp_path):
    path = tmp_path / "labels.jsonl"
    path.write_text('# comentario\n\n{"crop": "a.png"}\n\n', encoding="utf-8")

    assert eval_htr.read_jsonl(path) == [{"crop": "a.png"}]


def test_corrupt_line_fails_loudly_with_the_line_number(tmp_path):
    path = tmp_path / "labels.jsonl"
    path.write_text('{"crop": "a.png"}\nnao e json\n', encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        eval_htr.read_jsonl(path)

    assert ":2:" in str(excinfo.value)


def test_pairs_labels_with_predictions_by_crop_name(tmp_path):
    labels = _write(tmp_path / "l.jsonl", [{"crop": "a.png", "reference": "actina", "strata": ["bastao"]}])
    preds = _write(tmp_path / "p.jsonl", [{"crop": "a.png", "hypothesis": "actina", "confidence": "alta"}])

    samples = eval_htr.load_samples(labels, preds)

    assert samples[0].reference == "actina"
    assert samples[0].hypothesis == "actina"
    assert samples[0].confidence == "alta"
    assert samples[0].strata == ("bastao",)


def test_missing_prediction_counts_as_unread_not_as_a_skip(tmp_path):
    """Recorte sem predicao e o que aconteceria em producao se o pipeline falhasse ali."""
    labels = _write(tmp_path / "l.jsonl", [{"crop": "a.png", "reference": "actina"}])
    preds = _write(tmp_path / "p.jsonl", [])

    samples = eval_htr.load_samples(labels, preds)

    assert len(samples) == 1
    assert samples[0].hypothesis == ""


def test_empty_label_set_is_an_error(tmp_path):
    labels = _write(tmp_path / "l.jsonl", [])

    with pytest.raises(SystemExit):
        eval_htr.load_samples(labels, None)


def test_end_to_end_report_flags_uncalibrated_confidence(tmp_path, capsys):
    labels = _write(
        tmp_path / "l.jsonl",
        [
            {"crop": "a.png", "reference": "actina"},
            {"crop": "b.png", "reference": "miosina"},
            {"crop": "c.png", "reference": ""},
        ],
    )
    preds = _write(
        tmp_path / "p.jsonl",
        [
            {"crop": "a.png", "hypothesis": "actina", "confidence": "alta"},
            {"crop": "b.png", "hypothesis": "xxxxxxx", "confidence": "alta"},
            {"crop": "c.png", "hypothesis": "inventou", "confidence": "alta"},
        ],
    )

    report = eval_htr.evaluate(eval_htr.load_samples(labels, preds))
    eval_htr.print_report(report, "teste")

    out = capsys.readouterr().out
    assert "alucinacao em vazia" in out
    assert report.hallucination_rate == 1.0
