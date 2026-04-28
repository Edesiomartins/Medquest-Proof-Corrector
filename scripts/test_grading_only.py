from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def main() -> int:
    parser = argparse.ArgumentParser(description="Testa apenas correção textual discursiva.")
    parser.add_argument("--answer", required=True, help="Resposta transcrita do aluno.")
    parser.add_argument("--rubric", default=None, help="Rubrica em JSON ou caminho para arquivo JSON.")
    parser.add_argument("--question", default="Explique o conceito avaliado.")
    parser.add_argument("--confidence", default="media", choices=["alta", "media", "baixa"])
    parser.add_argument("--text-model", default=None)
    args = parser.parse_args()

    _load_backend_env()

    from app.services.exam_grading_client import grade_discursive_answer

    rubric = _load_rubric(args.rubric)
    result = grade_discursive_answer(
        {
            "number": 1,
            "prompt": args.question,
            "reading_confidence": args.confidence,
            "text_model": args.text_model,
        },
        rubric,
        args.answer,
        reading_confidence=args.confidence,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _load_rubric(raw: str | None) -> dict:
    if not raw:
        return {
            "max_score": 1.0,
            "expected_answer": "Resposta deve conter os conceitos essenciais do enunciado.",
            "essential_concepts": ["conceito essencial"],
        }
    possible_path = Path(raw)
    if possible_path.is_file():
        return json.loads(possible_path.read_text(encoding="utf-8"))
    return json.loads(raw)


def _load_backend_env() -> None:
    env_path = BACKEND / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    raise SystemExit(main())
