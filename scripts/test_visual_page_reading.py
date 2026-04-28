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
    parser = argparse.ArgumentParser(description="Testa leitura visual de uma página manuscrita.")
    parser.add_argument("image_path")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--vision-model", default=None)
    args = parser.parse_args()

    _load_backend_env()

    from app.services.openrouter_vision_client import extract_answers_from_page_image

    result = extract_answers_from_page_image(
        args.image_path,
        page_number=args.page,
        context={"vision_model": args.vision_model},
    )
    if "student" not in result or "questions" not in result:
        raise SystemExit("Resposta inválida: campos student/questions ausentes.")
    print(json.dumps(result, ensure_ascii=False, indent=2))
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
