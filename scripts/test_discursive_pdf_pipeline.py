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
    parser = argparse.ArgumentParser(description="Testa pipeline visual de PDF discursivo.")
    parser.add_argument("pdf_path")
    parser.add_argument("--page", default=None, help="Página 1-based ou lista separada por vírgula.")
    parser.add_argument("--rubric", default=None, help="Arquivo JSON com rubrica.")
    parser.add_argument("--output", default="discursive_pdf_pipeline_result.json")
    parser.add_argument("--vision-model", default=None)
    parser.add_argument("--text-model", default=None)
    args = parser.parse_args()

    _load_backend_env()

    from app.services.visual_exam_pipeline import analyze_discursive_exam_pdf

    rubric = json.loads(Path(args.rubric).read_text(encoding="utf-8")) if args.rubric else None
    result = analyze_discursive_exam_pdf(
        args.pdf_path,
        rubric=rubric,
        options={
            "process_pages": args.page,
            "vision_model": args.vision_model,
            "text_model": args.text_model,
        },
    )
    result.pop("_raw_students", None)
    output_path = Path(args.output)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nResultado salvo em: {output_path.resolve()}")
    return 0


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
