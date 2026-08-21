from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from PIL import Image

from app.core.config import settings
from app.services.exam_grading_client import grade_discursive_answer, grade_practical_answer
from app.services.exam_image_preprocess import maybe_crop_answer_regions, normalize_page_image
from app.services.openrouter_vision_client import (
    extract_answers_from_page_image,
    read_sheet_header,
    transcribe_answer_crop,
)
from app.services.pdf_page_renderer import render_pdf_to_images
from app.services.vision.ink import detect_ink, normalize_for_reading
from app.services.vision.qr_decode import decode_sheet_qr
from app.services.vision.sheet_geometry import DEFAULT_CROP_DPI, load_manifest, render_pdf_box

logger = logging.getLogger(__name__)

# DPI do recorte enviado ao modelo. Ver sheet_geometry: e o que poe a
# altura-de-x da cursiva perto de 37 px em vez dos ~8 px da pagina inteira.
CROP_DPI = DEFAULT_CROP_DPI
# Abaixo desta menor dimensao o recorte ganha upscale 2x Lanczos.
UPSCALE_CROP_BELOW_PX = 700
# Faixa superior da pagina onde ficam nome, matricula e turma.
HEADER_CROP_FRACTION = 0.22
# Guardas semanticas: detectam rubrica trocada comparando termos esperados com o
# texto da rubrica daquela questao. NAO existe default global -- termos fixos de
# um assunto zeravam indevidamente as questoes 1-3 de provas de outros assuntos
# (docs/HTR_PLANO_EXECUCAO.md, item P0-B). Configure por prova em
# `options["question_semantic_guards"]` ou `rubric["semantic_guards"]`,
# no formato {numero_da_questao: ["termo", ...]}.
QUESTION_SEMANTIC_GUARDS: dict[int, list[str]] = {}


def analyze_discursive_exam_pdf(
    pdf_path: str,
    rubric: dict | None = None,
    options: dict | None = None,
) -> dict:
    options = options or {}
    source = Path(pdf_path)
    work_dir = Path(tempfile.mkdtemp(prefix="visual_exam_"))
    warnings: list[str] = []
    errors: list[str] = []
    students: list[dict[str, Any]] = []
    vision_model_used = ""
    text_model_used = ""

    logger.info("Início do processamento visual do PDF: %s", source.name)
    started_total = time.perf_counter()

    try:
        page_images = render_pdf_to_images(
            str(source),
            str(work_dir / "pages"),
            dpi=int(options.get("dpi") or 220),
        )
        logger.info("Quantidade de páginas detectadas: %d", len(page_images))

        selected_pages = _selected_pages(options.get("process_pages"), len(page_images))
        if selected_pages:
            page_images_to_process = [
                (page_number, page_images[page_number - 1]) for page_number in selected_pages
            ]
        else:
            page_images_to_process = list(enumerate(page_images, start=1))

        rubric_map = _rubric_by_question(rubric)
        is_practical_exam = _is_practical_exam(rubric, options)
        semantic_guards = _semantic_guards_from(options, rubric)
        # Os recortes precisam sobreviver ao fim do processamento: sem a imagem,
        # a tela de revisão vira um campo de texto sem contexto e o revisor
        # aceita em vez de revisar. `work_dir` é temporário e some no `finally`.
        crop_dir = Path(options.get("crop_dir") or (work_dir / "crops"))
        manifest = load_manifest(options.get("layout_manifest"))
        if manifest is None and options.get("layout_manifest"):
            warnings.append(
                "Manifesto de layout ausente ou inválido; leitura por página inteira "
                "(resolução bem menor na área de resposta)."
            )

        for page_number, page_image in page_images_to_process:
            global_page_index = max(int(page_number) - 1, 0)
            physical_page_number = global_page_index + 1
            page_started = time.perf_counter()
            logger.info("Página processada: %d", physical_page_number)
            extracted_page = _read_page(
                pdf_path=str(source),
                page_image=page_image,
                page_index=global_page_index,
                physical_page_number=physical_page_number,
                manifest=manifest,
                options=options,
                rubric=rubric,
                work_dir=work_dir,
                crop_dir=crop_dir,
                warnings=warnings,
            )
            vision_model_used = vision_model_used or str(extracted_page.get("model_used") or "")
            if extracted_page.get("fallback_used"):
                warnings.append(f"Fallback de visão acionado na página {physical_page_number}.")
            model_reported_page = _to_int(extracted_page.get("physical_page"), default=physical_page_number)
            if model_reported_page != physical_page_number:
                logger.warning(
                    "[page-map] LLM retornou physical_page=%s; usando physical_page global=%s.",
                    model_reported_page,
                    physical_page_number,
                )
            physical_page = physical_page_number
            student_data = extracted_page.get("student") or {}
            detected_student_name = str(student_data.get("name") or "")
            detected_registration = str(student_data.get("registration") or "")
            detected_student_code = str(student_data.get("student_code") or "").strip() or _derive_student_code(
                detected_student_name,
                detected_registration,
            )

            page_questions = []
            answers_by_number: dict[int, dict[str, Any]] = {}
            for answer in extracted_page.get("questions") or []:
                qnum = int(answer.get("number") or 0)
                if qnum <= 0:
                    warnings.append(f"Questão sem número válido na página {physical_page_number}.")
                    continue
                if qnum in answers_by_number:
                    warnings.append(
                        f"Questão duplicada na leitura visual (Q{qnum}, página {physical_page_number}); mantendo primeira ocorrência."
                    )
                    continue
                answers_by_number[qnum] = answer

            for qnum in sorted(answers_by_number.keys()):
                question = answers_by_number[qnum]
                grade = _missing_rubric_grade(question)
                question_rubric = rubric_map.get(qnum) or (rubric if rubric and not rubric_map else None)
                correlation_id = (
                    f"{options.get('batch_id') or options.get('run_id') or 'visual'}:"
                    f"{detected_student_code or detected_registration or detected_student_name or 'anonymous'}:"
                    f"{physical_page_number}:Q{qnum}"
                )
                question_prompt = (
                    (question_rubric or {}).get("prompt")
                    or (question_rubric or {}).get("question")
                    or (question_rubric or {}).get("question_text")
                    or ""
                )
                rubric_preview = (
                    (question_rubric or {}).get("expected_answer")
                    or (question_rubric or {}).get("rubric")
                    or ""
                )
                logger.warning(
                    "[grading-map-debug] correlation_id=%s student=%s page=%s q=%s question_title=%s answer_preview=%s rubric_preview=%s",
                    correlation_id,
                    detected_student_name or detected_registration or "n/a",
                    physical_page_number,
                    qnum,
                    str(question_prompt)[:120] if question_prompt else None,
                    str(question.get("answer_transcription") or "")[:120],
                    str(rubric_preview)[:120] if rubric_preview else None,
                )
                if question.get("reading_failed"):
                    # Sem transcrição não há o que corrigir: gastar chamada de
                    # correção aqui só produziria um zero com aparência de nota.
                    grade = _grading_error(question, str(question.get("reading_notes") or "Falha na leitura."))
                    text_model_used = text_model_used or str(options.get("text_model") or "")
                elif question_rubric:
                    if is_practical_exam:
                        grade = grade_practical_answer(
                            {
                                **question,
                                "max_score": (question_rubric or {}).get("max_score"),
                                "student_name": detected_student_name,
                                "registration": detected_registration,
                                "global_page_index": global_page_index,
                                "physical_page_number": physical_page_number,
                                "correlation_id": correlation_id,
                            },
                            question_rubric,
                            question.get("answer_transcription") or "",
                            reading_confidence=question.get("reading_confidence") or "media",
                        )
                        text_model_used = text_model_used or str(grade.get("model_used") or "practical-rule-based")
                    elif not _semantic_guard_matches(qnum, question_rubric, guards=semantic_guards):
                        message = (
                            f"Possível troca de rubrica para question_number={qnum} "
                            f"(página {physical_page_number})."
                        )
                        warnings.append(message)
                        grade = {
                            "question_number": qnum,
                            "score": 0.0,
                            "max_score": float((question_rubric or {}).get("max_score") or 1.0),
                            "verdict": "incorreta",
                            "justification": "Rubrica suspeita para esta questão. Revisão manual obrigatória.",
                            "detected_concepts": [],
                            "missing_concepts": [],
                            "needs_human_review": True,
                            "review_reason": message,
                            "schema_valid": False,
                            "parse_warnings": [message],
                            "expected_answer": str((question_rubric or {}).get("expected_answer") or ""),
                        }
                        text_model_used = text_model_used or str(options.get("text_model") or "")
                        page_questions.append(
                            {
                                "physical_page": physical_page,
                                "detected_student_name": detected_student_name,
                                "detected_registration": detected_registration,
                                "detected_student_code": detected_student_code,
                                "number": qnum,
                                "question_number": qnum,
                                "prompt_detected": question.get("prompt_detected", ""),
                                "extracted_answer": question.get("answer_transcription", ""),
                                "answer_transcription": question.get("answer_transcription", ""),
                                "reading_confidence": question.get("reading_confidence", "baixa"),
                                "ocr_confidence": question.get("ocr_confidence"),
                                "reading_notes": question.get("reading_notes", ""),
                                "has_answer": bool(question.get("has_answer", False)),
                                "image_region": question.get("image_region"),
                                "answer_crop_path": question.get("answer_crop_path"),
                                "ink_ratio": question.get("ink_ratio"),
                                "grade": _public_grade(grade),
                                "raw_grading_json": grade,
                            }
                        )
                        continue
                    else:
                        try:
                            grade = grade_discursive_answer(
                                {
                                    **question,
                                    "text_model": options.get("text_model"),
                                    "student_name": detected_student_name,
                                    "registration": detected_registration,
                                    "global_page_index": global_page_index,
                                    "physical_page_number": physical_page_number,
                                    "correlation_id": correlation_id,
                                },
                                question_rubric,
                                question.get("answer_transcription") or "",
                                reading_confidence=question.get("reading_confidence") or "media",
                            )
                            text_model_used = text_model_used or str(grade.get("model_used") or "")
                            if grade.get("fallback_used"):
                                warnings.append(
                                    f"Fallback textual acionado na página {physical_page_number}, questão {qnum}."
                                )
                        except Exception as exc:
                            message = f"Correção textual falhou na página {physical_page_number}, questão {qnum}: {exc}"
                            logger.warning(message)
                            warnings.append(message)
                            grade = _grading_error(question, str(exc))
                elif rubric:
                    warnings.append(f"Rubrica ausente para a questão {qnum} na página {physical_page_number}.")

                if question.get("reading_confidence") == "baixa" or grade.get("needs_human_review"):
                    logger.info("Página %d, questão %d precisa de revisão humana.", physical_page_number, qnum)

                if question_rubric and not grade.get("expected_answer"):
                    grade["expected_answer"] = str((question_rubric or {}).get("expected_answer") or "")

                page_questions.append(
                    {
                        "physical_page": physical_page,
                        "detected_student_name": detected_student_name,
                        "detected_registration": detected_registration,
                        "detected_student_code": detected_student_code,
                        "number": qnum,
                        "question_number": qnum,
                        "prompt_detected": question.get("prompt_detected", ""),
                        "extracted_answer": question.get("answer_transcription", ""),
                        "answer_transcription": question.get("answer_transcription", ""),
                        "reading_confidence": question.get("reading_confidence", "baixa"),
                        "ocr_confidence": question.get("ocr_confidence"),
                        "reading_notes": question.get("reading_notes", ""),
                        "has_answer": bool(question.get("has_answer", False)),
                        "image_region": question.get("image_region"),
                        "answer_crop_path": question.get("answer_crop_path"),
                        "ink_ratio": question.get("ink_ratio"),
                        "grade": _public_grade(grade),
                        "raw_grading_json": grade,
                    }
                )

            print("=== DEBUG STUDENT PAGE MAP ===")
            print("physical_page:", physical_page)
            print("detected_student_name:", detected_student_name)
            print("detected_registration:", detected_registration)
            print("questions_found:", [q.get("number") for q in page_questions])
            print(
                "answer_preview_q1:",
                (page_questions[0].get("answer_transcription") or "")[:120] if page_questions else None,
            )
            print("==============================")

            students.append(
                {
                    "student": {
                        **student_data,
                        "student_code": detected_student_code,
                    },
                    "page": physical_page_number,
                    "physical_page": physical_page,
                    "detected_student_name": detected_student_name,
                    "detected_registration": detected_registration,
                    "detected_student_code": detected_student_code,
                    "questions": page_questions,
                    "raw_vision_json": extracted_page,
                }
            )
            logger.info(
                "Tempo de resposta por página",
                extra={"page": physical_page_number, "elapsed_seconds": round(time.perf_counter() - page_started, 3)},
            )

        result = {
            "status": "success",
            "pdf_name": source.name,
            "pages_processed": len(page_images_to_process),
            "vision_model_used": vision_model_used or options.get("vision_model") or settings.OPENROUTER_VISION_MODEL,
            "text_model_used": text_model_used or options.get("text_model") or settings.OPENROUTER_TEXT_MODEL,
            "students": _strip_internal_raw(students),
            "warnings": warnings,
            "errors": errors,
        }
        audit_path = work_dir / "visual_exam_result.json"
        audit_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(
            "Processamento visual concluído",
            extra={"elapsed_seconds": round(time.perf_counter() - started_total, 3)},
        )
        return {**result, "_raw_students": students}
    except Exception as exc:
        logger.exception("Falha no pipeline de leitura visual.")
        return {
            "status": "error",
            "pdf_name": source.name,
            "pages_processed": 0,
            "vision_model_used": vision_model_used,
            "text_model_used": text_model_used,
            "students": [],
            "warnings": warnings,
            "errors": [str(exc)],
        }
    finally:
        if not _debug_enabled():
            shutil.rmtree(work_dir, ignore_errors=True)


def _selected_pages(raw: Any, total_pages: int) -> list[int]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, int):
        pages = [raw]
    elif isinstance(raw, str):
        pages = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            pages.append(int(part))
    elif isinstance(raw, list):
        pages = [int(page) for page in raw]
    else:
        return []
    return sorted({page for page in pages if 1 <= page <= total_pages})


def _rubric_by_question(payload: Any) -> dict[int, dict]:
    if not payload:
        return {}
    if isinstance(payload, dict):
        if isinstance(payload.get("questions"), list):
            return _rubric_by_question(payload["questions"])
        mapped: dict[int, dict] = {}
        for key, value in payload.items():
            try:
                mapped[int(key)] = value if isinstance(value, dict) else {"rubric": value}
            except (TypeError, ValueError):
                continue
        return mapped
    if isinstance(payload, list):
        mapped = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            qnum = item.get("number") or item.get("question_number") or item.get("questao")
            try:
                mapped[int(qnum)] = item
            except (TypeError, ValueError):
                continue
        return mapped
    return {}


def _question_outline_for_transcription(payload: Any) -> Any:
    """Contexto minimo e CEGO para a etapa de visao.

    Devolve apenas numeracao, enunciado e valor da questao -- dados que ja estao
    impressos na propria folha. O gabarito (`expected_answer`, `rubric`,
    `correction_criteria`) fica de fora: se o modelo o le antes de transcrever,
    ele completa palavras ilegiveis com a resposta esperada, infla a nota e
    esconde as falhas de leitura (docs/HTR_PLANO_EXECUCAO.md, item P0-A).
    """
    if isinstance(payload, dict) and isinstance(payload.get("questions"), list):
        return {"questions": [_compact_question(item) for item in payload["questions"][:20]]}
    if isinstance(payload, list):
        return {"questions": [_compact_question(item) for item in payload[:20] if isinstance(item, dict)]}
    if isinstance(payload, dict):
        return {"question_keys": list(payload.keys())[:20]}
    return None


def _is_practical_exam(rubric: Any, options: dict | None) -> bool:
    if isinstance(options, dict) and options.get("is_practical"):
        return True
    return isinstance(rubric, dict) and bool(rubric.get("is_practical"))


def _compact_question(item: dict) -> dict:
    """Somente o que ja esta visivel na folha impressa. Sem gabarito."""
    return {
        "number": item.get("number") or item.get("question_number") or item.get("questao"),
        "prompt": item.get("prompt") or item.get("question") or item.get("enunciado") or "",
        "max_score": item.get("max_score") or item.get("valor") or 1.0,
    }


def _missing_rubric_grade(question: dict) -> dict:
    confidence = str(question.get("reading_confidence") or "media")
    return {
        "question_number": int(question.get("number") or 0),
        "score": None,
        "max_score": None,
        "verdict": "sem_rubrica",
        "justification": "Rubrica não fornecida para esta questão; correção textual não executada.",
        "detected_concepts": [],
        "missing_concepts": [],
        "needs_human_review": confidence == "baixa",
        "review_reason": "Leitura visual com baixa confiança." if confidence == "baixa" else "",
    }


def _grading_error(question: dict, error: str) -> dict:
    return {
        "question_number": int(question.get("number") or 0),
        "score": 0.0,
        "max_score": None,
        "verdict": "ilegivel" if question.get("reading_confidence") == "baixa" else "incorreta",
        "justification": "Falha técnica na correção textual automática.",
        "detected_concepts": [],
        "missing_concepts": [],
        "needs_human_review": True,
        "review_reason": error[:500],
    }


def _public_grade(grade: dict) -> dict:
    return {
        "question_number": grade.get("question_number"),
        "score": grade.get("score"),
        "max_score": grade.get("max_score"),
        "verdict": grade.get("verdict"),
        "justification": grade.get("justification"),
        "detected_concepts": grade.get("detected_concepts", []),
        "missing_concepts": grade.get("missing_concepts", []),
        "needs_human_review": bool(grade.get("needs_human_review", False)),
        "review_reason": grade.get("review_reason", ""),
        "model_used": grade.get("model_used"),
        "expected_answer": grade.get("expected_answer", ""),
    }


def _strip_internal_raw(students: list[dict]) -> list[dict]:
    clean_students = []
    for student in students:
        clean_questions = []
        for question in student.get("questions") or []:
            clean_question = {key: value for key, value in question.items() if key != "raw_grading_json"}
            clean_questions.append(clean_question)
        clean_students.append(
            {
                "student": student.get("student") or {},
                "page": student.get("page"),
                "physical_page": student.get("physical_page"),
                "detected_student_name": student.get("detected_student_name"),
                "detected_registration": student.get("detected_registration"),
                "detected_student_code": student.get("detected_student_code"),
                "questions": clean_questions,
            }
        )
    return clean_students


def _debug_enabled() -> bool:
    return os.getenv("DEBUG", "").strip().lower() in {"1", "true", "yes"}


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _semantic_guards_from(options: Any, rubric: Any) -> dict[int, list[str]]:
    """Le as guardas semanticas configuradas para esta prova."""
    raw: Any = None
    if isinstance(options, dict):
        raw = options.get("question_semantic_guards")
    if raw is None and isinstance(rubric, dict):
        raw = rubric.get("semantic_guards")
    if not isinstance(raw, dict):
        return dict(QUESTION_SEMANTIC_GUARDS)

    guards: dict[int, list[str]] = {}
    for key, terms in raw.items():
        try:
            qnum = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(terms, str):
            terms = [terms]
        if not isinstance(terms, (list, tuple)):
            continue
        clean = [str(term).strip().lower() for term in terms if str(term).strip()]
        if clean:
            guards[qnum] = clean
    return guards


def _semantic_guard_matches(
    question_number: int,
    question_rubric: dict | None,
    guards: dict[int, list[str]] | None = None,
) -> bool:
    if guards is None:
        guards = dict(QUESTION_SEMANTIC_GUARDS)
    expected_terms = guards.get(question_number)
    if not expected_terms:
        return True
    if not question_rubric:
        return False
    text_blob = " ".join(
        [
            str(question_rubric.get("prompt") or ""),
            str(question_rubric.get("question_text") or ""),
            str(question_rubric.get("expected_answer") or ""),
            str(question_rubric.get("correction_criteria") or ""),
            str(question_rubric.get("rubric") or ""),
        ]
    ).lower()
    return any(term in text_blob for term in expected_terms)


def _derive_student_code(name: str, registration: str) -> str:
    for source in (name, registration):
        text = str(source or "").strip()
        if not text:
            continue
        match = re.search(r"(?i)aluno\D*(\d{1,4})", text)
        if match:
            return f"{int(match.group(1)):03d}"
        reg_match = re.search(r"(\d{2,4})\s*$", text)
        if reg_match:
            return f"{int(reg_match.group(1)):03d}"
    return ""


# ---------------------------------------------------------------------------
# Leitura da página: por recorte de caixa quando há manifesto, página inteira
# quando não há. Ver docs/HTR_PLANO_EXECUCAO.md, item 4.
# ---------------------------------------------------------------------------


def _read_page(
    *,
    pdf_path: str,
    page_image: str,
    page_index: int,
    physical_page_number: int,
    manifest: Any,
    options: dict,
    rubric: Any,
    work_dir: Path,
    crop_dir: Path,
    warnings: list[str],
) -> dict:
    """Escolhe a rota de leitura e devolve sempre o mesmo formato de página.

    Manter o formato de saída idêntico nas duas rotas é o que permite que todo o
    resto do pipeline — mapeamento de aluno, correção, persistência — não saiba
    qual delas rodou.
    """
    manifest_page = manifest.page(page_index) if manifest else None
    if manifest_page is not None and manifest_page.has_boxes:
        return _read_page_by_crops(
            pdf_path=pdf_path,
            page_image=page_image,
            page_index=page_index,
            physical_page_number=physical_page_number,
            manifest_page=manifest_page,
            options=options,
            crop_dir=crop_dir,
            warnings=warnings,
        )

    if manifest is not None:
        warnings.append(
            f"Página {physical_page_number} não está no manifesto; lida como página inteira."
        )
    return _read_page_whole(
        page_image=page_image,
        physical_page_number=physical_page_number,
        options=options,
        rubric=rubric,
    )


def _read_page_whole(
    *,
    page_image: str,
    physical_page_number: int,
    options: dict,
    rubric: Any,
) -> dict:
    """Rota legada: a página inteira vai ao modelo.

    Vale para provas geradas antes do manifesto. Entrega bem menos resolução por
    milímetro de papel — é exatamente o que o item 4 existe para evitar — mas é
    melhor do que não ler a prova.
    """
    normalized_image = normalize_page_image(page_image)
    crop_info = maybe_crop_answer_regions(normalized_image)

    return extract_answers_from_page_image(
        normalized_image,
        page_number=physical_page_number,
        context={
            "vision_model": options.get("vision_model"),
            # Transcrição é CEGA: nunca enviar gabarito/critérios para a etapa de
            # visão (docs/HTR_PLANO_EXECUCAO.md, item P0-A).
            "question_outline": _question_outline_for_transcription(rubric),
            "detected_answer_regions": len(crop_info.get("regions") or []),
        },
    )


def _read_page_by_crops(
    *,
    pdf_path: str,
    page_image: str,
    page_index: int,
    physical_page_number: int,
    manifest_page: Any,
    options: dict,
    crop_dir: Path,
    warnings: list[str],
) -> dict:
    """Uma chamada por questão, sobre o recorte da própria caixa de resposta.

    Três coisas mudam de patamar aqui:

    1. **Resolução.** O recorte é rasterizado direto do PDF a ~380 DPI, então a
       altura-de-x da cursiva chega ao modelo com ~37 px em vez dos ~8 px que
       sobravam da página inteira reduzida.
    2. **Caixa vazia não custa nada.** O detector de tinta resolve antes de
       qualquer chamada, o que elimina a nota atribuída a resposta inexistente.
    3. **Um objetivo por chamada.** Numeração vem da geometria, não da leitura;
       identidade sai do QR ou de um recorte de cabeçalho separado.
    """
    crop_dir.mkdir(parents=True, exist_ok=True)

    questions: list[dict[str, Any]] = []
    model_used = ""
    fallback_used = False

    for box in manifest_page.boxes:
        qnum = box.question_number
        try:
            crop = render_pdf_box(pdf_path, page_index, box, dpi=CROP_DPI)
        except Exception as exc:
            message = f"Falha ao recortar a questão {qnum} na página {physical_page_number}: {exc}"
            logger.warning(message)
            warnings.append(message)
            questions.append(_failed_reading_question(qnum, "", str(exc), None))
            continue

        ink = detect_ink(crop)
        crop_path = crop_dir / f"p{physical_page_number:03d}_q{qnum:02d}.png"

        if not ink.has_ink:
            crop.save(crop_path, format="PNG", optimize=True)
            if ink.is_marginal:
                warnings.append(
                    f"Página {physical_page_number}, questão {qnum}: densidade de tinta marginal; "
                    "confirmar se a caixa está mesmo vazia."
                )
            questions.append(_blank_answer_question(qnum, ink, str(crop_path)))
            continue

        prepared = normalize_for_reading(crop, upscale_below_px=UPSCALE_CROP_BELOW_PX)
        prepared.save(crop_path, format="PNG", optimize=True)

        try:
            question = transcribe_answer_crop(
                str(crop_path),
                question_number=qnum,
                vision_model=options.get("vision_model"),
            )
        except Exception as exc:
            message = f"Transcrição falhou na página {physical_page_number}, questão {qnum}: {exc}"
            logger.warning(message)
            warnings.append(message)
            # A caixa TEM tinta: descartar a questão faria a resposta do aluno
            # sumir do resultado deixando só um aviso no log. Ela vai adiante
            # marcada para revisão humana.
            questions.append(_failed_reading_question(qnum, str(crop_path), str(exc), ink))
            continue

        question["answer_crop_path"] = str(crop_path)
        question["ink_ratio"] = round(ink.ink_ratio, 5)
        questions.append(question)

        model_used = model_used or str(question.get("model_used") or "")
        fallback_used = fallback_used or bool(question.get("fallback_used"))

    student = _identify_page(
        page_image=page_image,
        manifest_page=manifest_page,
        physical_page_number=physical_page_number,
        options=options,
        crop_dir=crop_dir,
        warnings=warnings,
    )

    return {
        "student": student,
        "physical_page": physical_page_number,
        "questions": questions,
        "model_used": model_used,
        "fallback_used": fallback_used,
        "read_strategy": "manifest_crops",
    }


def _blank_answer_question(question_number: int, ink: Any, crop_path: str) -> dict:
    """Caixa sem tinta, resolvida sem chamar modelo nenhum."""
    return {
        "number": question_number,
        "prompt_detected": "",
        "answer_transcription": "",
        "reading_confidence": "alta",
        "ocr_confidence": None,
        "reading_notes": f"Sem resposta detectada na caixa ({ink.reason}).",
        "has_answer": False,
        "image_region": None,
        "answer_crop_path": crop_path,
        "ink_ratio": round(ink.ink_ratio, 5),
        "ink_marginal": bool(ink.is_marginal),
        "model_used": "",
        "fallback_used": False,
    }


def _identify_page(
    *,
    page_image: str,
    manifest_page: Any,
    physical_page_number: int,
    options: dict,
    crop_dir: Path,
    warnings: list[str],
) -> dict:
    """Identidade da página: QR primeiro, cabeçalho só se o QR falhar.

    O QR carrega `MQPC|exam_id|student_id|page|total` e é conferível; extrair o
    número do aluno com regex sobre o nome lido pelo modelo é adivinhação quando
    existe um QR impresso na mesma página. Quando o QR resolve, a chamada de
    leitura de cabeçalho nem acontece.
    """
    identity: dict[str, Any] = {
        "name": "",
        "registration": "",
        "class": "",
        "student_code": "",
        "qr_student_id": "",
        "identity_source": "unknown",
    }

    try:
        with Image.open(page_image) as page:
            payload = decode_sheet_qr(page)
    except Exception as exc:
        logger.warning("Falha ao decodificar QR da página %d: %s", physical_page_number, exc)
        payload = None

    if payload is not None:
        identity["qr_student_id"] = payload.student_id
        identity["identity_source"] = "qr"
    elif manifest_page is not None and manifest_page.student_id:
        identity["qr_student_id"] = manifest_page.student_id
        identity["identity_source"] = "manifest"

    # O nome legível ainda vem do cabeçalho — o QR só carrega o UUID do aluno.
    header_path = _save_header_crop(page_image, crop_dir, physical_page_number)
    if header_path:
        try:
            header = read_sheet_header(header_path, vision_model=options.get("vision_model"))
            identity.update(
                {
                    "name": header.get("name") or "",
                    "registration": header.get("registration") or "",
                    "class": header.get("class") or "",
                    "student_code": header.get("student_code") or "",
                }
            )
            if identity["identity_source"] == "unknown":
                identity["identity_source"] = "header_ocr"
        except Exception as exc:
            message = f"Leitura do cabeçalho falhou na página {physical_page_number}: {exc}"
            logger.warning(message)
            warnings.append(message)

    return identity


def _save_header_crop(page_image: str, crop_dir: Path, physical_page_number: int) -> str | None:
    """Recorta a faixa superior da página, onde ficam nome, matrícula e turma."""
    try:
        with Image.open(page_image) as page:
            height = int(page.height * HEADER_CROP_FRACTION)
            header = page.convert("RGB").crop((0, 0, page.width, max(1, height)))
        crop_dir.mkdir(parents=True, exist_ok=True)
        path = crop_dir / f"p{physical_page_number:03d}_header.png"
        normalize_for_reading(header).save(path, format="PNG", optimize=True)
        return str(path)
    except Exception as exc:
        logger.warning("Falha ao recortar cabeçalho da página %d: %s", physical_page_number, exc)
        return None


def _failed_reading_question(
    question_number: int,
    crop_path: str,
    error: str,
    ink: Any,
) -> dict:
    """Caixa com tinta cuja leitura falhou: segue para revisão, não some.

    Distinta da caixa vazia: aqui existe resposta escrita e ela não foi lida. O
    revisor precisa ver o recorte; zerar em silêncio seria trocar uma falha de
    infraestrutura por uma nota.
    """
    return {
        "number": question_number,
        "prompt_detected": "",
        "answer_transcription": "",
        "reading_confidence": "baixa",
        "ocr_confidence": None,
        "reading_notes": f"Falha na leitura desta questão: {error}",
        "has_answer": True,
        "image_region": None,
        "answer_crop_path": crop_path or None,
        "ink_ratio": round(ink.ink_ratio, 5) if ink is not None else None,
        "reading_failed": True,
        "model_used": "",
        "fallback_used": False,
    }
