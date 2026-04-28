from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def parse_json_safely(raw_output: str) -> dict[str, Any]:
    text = (raw_output or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0].strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as direct_error:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            logger.error("JSON inválido retornado pelo modelo: %s", direct_error)
            return {
                "status": "error",
                "error": "invalid_json",
                "raw_model_output": raw_output,
            }
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as sliced_error:
            logger.error("JSON inválido mesmo após extração: %s", sliced_error)
            return {
                "status": "error",
                "error": "invalid_json",
                "raw_model_output": raw_output,
            }

    if not isinstance(parsed, dict):
        return {
            "status": "error",
            "error": "json_root_not_object",
            "raw_model_output": raw_output,
        }
    return parsed
