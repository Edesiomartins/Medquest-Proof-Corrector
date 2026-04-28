"""Pipeline de OCR + correção por questão com revisão apenas para exceções."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from reportlab.lib.pagesizes import A4

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.storage import path_from_local_url
from app.models.exam import Exam, ExamQuestion
from app.models.grading import QuestionScore, ResultStatus, StudentResult
from app.models.pipeline import BatchStatus, UploadBatch
from app.models.student import Student
from app.services.generator.sheet_layout import pdf_answer_box_to_pil_pixels
from app.services.grading.manual_review_decision import decide_manual_review
from app.services.llm.grading import QuestionSpec, SingleQuestionGrade, TextGradingService
from app.services.vision.ocr import get_ocr_provider, image_to_png_bytes
from app.services.vision.page_align import align_scan_page
from app.services.vision.pdf_parser import PDFParserService
from app.services.vision.qr_decode import PageQrPayload, decode_sheet_qr

logger = logging.getLogger(__name__)

PAGE_W_PT, PAGE_H_PT = A4
PIPELINE_DPI = 200


def _fail(db, batch: UploadBatch, msg: str) -> None:
    logger.error(msg)
    batch.status = BatchStatus.FAILED
    db.commit()


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _effective_total(scores: list[QuestionScore]) -> float:
    total = 0.0
    for s in scores:
        if s.final_score is not None:
            total += float(s.final_score)
        elif not s.requires_manual_review:
            total += float(s.ai_score or 0)
        else:
            total += float(s.ai_score or 0)
    return total


def _annotate_json(criteria: list[str] | None) -> str | None:
    if not criteria:
        return None
    return json.dumps(criteria, ensure_ascii=False)


def _parse_manifest(raw: str | None) -> dict[int, dict[str, Any]] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Manifest JSON inválido na prova.")
        return None
    pages = data.get("pages") or []
    return {int(p["physical_index"]): p for p in pages}


def _pick_student_id(
    qr: PageQrPayload | None,
    manifest_student: str | None,
    fallback_order: list[Student],
    page_idx: int,
    exam_id_str: str,
) -> UUID | None:
    if qr and qr.exam_id != exam_id_str:
        logger.warning(
            "QR exam_id diferente da prova (QR=%s, esperado=%s).",
            qr.exam_id,
            exam_id_str,
        )
    if qr:
        try:
            return UUID(qr.student_id)
        except ValueError:
            pass
    if manifest_student:
        try:
            return UUID(manifest_student)
        except ValueError:
            pass
    if page_idx < len(fallback_order):
        return fallback_order[page_idx].id
    return None


@celery_app.task(bind=True, max_retries=0)
def process_upload_batch(self, batch_id: str):
    db = SessionLocal()
    try:
        batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        if not batch:
            logger.warning("Batch %s não encontrado.", batch_id)
            return

        exam = db.query(Exam).filter(Exam.id == batch.exam_id).first()
        if not exam:
            _fail(db, batch, f"[batch={batch_id}] Prova não encontrada.")
            return

        questions = (
            db.query(ExamQuestion)
            .filter(ExamQuestion.exam_id == exam.id)
            .order_by(ExamQuestion.question_number)
            .all()
        )
        if not questions:
            _fail(db, batch, f"[batch={batch_id}] Prova sem questões.")
            return

        question_by_number = {q.question_number: q for q in questions}
        question_specs = {
            q.question_number: QuestionSpec(
                question_number=q.question_number,
                question_text=q.question_text,
                expected_answer=q.expected_answer,
                max_score=q.max_score,
            )
            for q in questions
        }

        students_ordered: list[Student] = []
        if exam.class_id:
            students_ordered = (
                db.query(Student)
                .filter(Student.class_id == exam.class_id)
                .order_by(Student.registration_number)
                .all()
            )

        manifest_by_page = _parse_manifest(exam.layout_manifest_json)

        batch.status = BatchStatus.PROCESSING
        db.commit()

        try:
            pdf_path = path_from_local_url(batch.file_url)
        except ValueError:
            _fail(db, batch, f"[batch={batch_id}] URL inválida: {batch.file_url!r}")
            return

        if not pdf_path.is_file():
            _fail(db, batch, f"[batch={batch_id}] Arquivo não encontrado: {pdf_path}")
            return

        pdf_bytes = pdf_path.read_bytes()
        try:
            page_images = PDFParserService.extract_pages_as_images(pdf_bytes, dpi=PIPELINE_DPI)
            batch.total_pages = len(page_images)
            db.commit()
        except Exception as exc:
            _fail(db, batch, f"[batch={batch_id}] Falha ao ler PDF: {exc}")
            return

        logger.info("[batch=%s] %d páginas extraídas.", batch_id, len(page_images))

        ocr_provider = get_ocr_provider()
        exam_id_str = str(exam.id)

        student_results_by_id: dict[UUID, StudentResult] = {}
        anonymous_results_by_page: dict[int, StudentResult] = {}

        def get_or_create_sr(student_pk: UUID | None, page_idx: int) -> StudentResult:
            page_one_based = page_idx + 1
            if student_pk:
                if student_pk in student_results_by_id:
                    sr = student_results_by_id[student_pk]
                    sr.page_number = min(sr.page_number, page_one_based)
                    return sr
                sr = StudentResult(
                    batch_id=batch.id,
                    student_id=student_pk,
                    page_number=page_one_based,
                    status=ResultStatus.PENDING,
                )
                db.add(sr)
                db.flush()
                student_results_by_id[student_pk] = sr
                return sr

            if page_idx in anonymous_results_by_page:
                return anonymous_results_by_page[page_idx]

            sr = StudentResult(
                batch_id=batch.id,
                student_id=None,
                page_number=page_one_based,
                status=ResultStatus.PENDING,
            )
            db.add(sr)
            db.flush()
            anonymous_results_by_page[page_idx] = sr
            return sr

        def process_crop_for_question(
            *,
            sr: StudentResult,
            eq: ExamQuestion,
            crop_bytes: bytes,
            physical_page_one_based: int,
            alignment_failed: bool,
            fallback_visual_ok: bool,
            crop_box_json: str | None = None,
        ) -> QuestionScore:
            ocr_result = _run_async(ocr_provider.extract_handwriting(crop_bytes))
            spec = question_specs[eq.question_number]
            if ocr_result.error_message:
                grade = SingleQuestionGrade(
                    question_number=eq.question_number,
                    score=0.0,
                    justification="",
                    grading_confidence=1.0,
                    manual_review_required=True,
                    manual_review_reason=ocr_result.error_message,
                )
                parse_ok = True
            else:
                grade_tuple = _run_async(TextGradingService.grade_single_question(ocr_result.text, spec))
                grade = grade_tuple[0]
                parse_ok = grade_tuple[1]

            review, reason = decide_manual_review(
                ocr_result,
                grade,
                ocr_result.text,
                eq.max_score,
                json_parse_failed=not parse_ok,
                fallback_visual_ok=fallback_visual_ok or (not ocr_result.needs_fallback),
                alignment_failed=alignment_failed,
                score_parse_invalid=not parse_ok,
            )

            criteria_met = grade.criteria_met or []
            criteria_miss = grade.criteria_missing or []

            qs = QuestionScore(
                student_result_id=sr.id,
                question_id=eq.id,
                ai_score=grade.score,
                ai_justification=grade.justification or None,
                final_score=(grade.score if not review else None),
                extracted_answer_text=ocr_result.text or None,
                ocr_provider=ocr_result.provider,
                ocr_confidence=ocr_result.confidence_avg,
                grading_confidence=grade.grading_confidence,
                requires_manual_review=review,
                manual_review_reason=(reason if review else None),
                criteria_met_json=_annotate_json(criteria_met),
                criteria_missing_json=_annotate_json(criteria_miss),
                source_page_number=physical_page_one_based,
                source_question_number=eq.question_number,
                crop_box_json=crop_box_json,
            )
            db.add(qs)
            return qs

        # --- Processamento por página física ---
        for page_idx, page_img in enumerate(page_images):
            aligned_img, align_ok, _align_reason = align_scan_page(page_img)
            alignment_failed = not align_ok

            qr_payload = decode_sheet_qr(aligned_img)
            manifest_row = manifest_by_page.get(page_idx) if manifest_by_page else None
            manifest_student = manifest_row["student_id"] if manifest_row else None

            student_uuid = _pick_student_id(
                qr_payload,
                manifest_student,
                students_ordered,
                page_idx,
                exam_id_str,
            )

            sr = get_or_create_sr(student_uuid, page_idx)

            use_manifest = manifest_row is not None and manifest_row.get("boxes")

            if alignment_failed:
                logger.warning("[batch=%s] Alinhamento da página %d falhou.", batch_id, page_idx + 1)

            if use_manifest:
                boxes = manifest_row["boxes"]
                if not qr_payload:
                    logger.info(
                        "[batch=%s] Página %d sem QR legível — usando manifest/student fallback.",
                        batch_id,
                        page_idx + 1,
                    )

                scores_this_page: list[QuestionScore] = []

                for box in boxes:
                    qnum = int(box["question_number"])
                    eq = question_by_number.get(qnum)
                    if not eq:
                        continue
                    left, upper, right, lower = pdf_answer_box_to_pil_pixels(
                        box["x_pt"],
                        box["y_bottom_pt"],
                        box["width_pt"],
                        box["height_pt"],
                        PAGE_H_PT,
                        PIPELINE_DPI,
                    )

                    crop = aligned_img.crop((left, upper, right, lower))
                    crop_bytes = image_to_png_bytes(crop)

                    qs = process_crop_for_question(
                        sr=sr,
                        eq=eq,
                        crop_bytes=crop_bytes,
                        physical_page_one_based=page_idx + 1,
                        alignment_failed=alignment_failed,
                        fallback_visual_ok=False,
                        crop_box_json=json.dumps(box, ensure_ascii=False),
                    )
                    scores_this_page.append(qs)

                if alignment_failed:
                    for qs in scores_this_page:
                        qs.requires_manual_review = True
                        qs.manual_review_reason = qs.manual_review_reason or (
                            "Falha no alinhamento/crop da página."
                        )
                        qs.final_score = None
                db.commit()

            else:
                # --- Legado: OCR da página inteira + mesma transcrição por questão ---
                logger.warning(
                    "[batch=%s] Manifest ausente ou página %d não mapeada — modo legado.",
                    batch_id,
                    page_idx + 1,
                )

                legacy_student = (
                    students_ordered[page_idx].id if page_idx < len(students_ordered) else None
                )
                sr_legacy = get_or_create_sr(legacy_student, page_idx)

                img_bytes = image_to_png_bytes(aligned_img)
                ocr_full = _run_async(ocr_provider.extract_handwriting(img_bytes))

                for eq in questions:
                    spec = question_specs[eq.question_number]
                    grade_tuple = _run_async(
                        TextGradingService.grade_single_question(ocr_full.text, spec)
                    )
                    grade = grade_tuple[0]
                    parse_ok = grade_tuple[1]

                    review, reason = decide_manual_review(
                        ocr_full,
                        grade,
                        ocr_full.text,
                        eq.max_score,
                        json_parse_failed=not parse_ok,
                        fallback_visual_ok=False,
                        alignment_failed=alignment_failed,
                        score_parse_invalid=not parse_ok,
                    )

                    mr_reason = None
                    if review:
                        mr_reason = reason or "Revisão manual necessária."
                        if not exam.layout_manifest_json:
                            mr_reason = (
                                f"{mr_reason} Compatibilidade sem manifesto salvo "
                                "(OCR da página inteira para todas as questões)."
                            )

                    qs = QuestionScore(
                        student_result_id=sr_legacy.id,
                        question_id=eq.id,
                        ai_score=grade.score,
                        ai_justification=grade.justification or None,
                        final_score=(None if review else grade.score),
                        extracted_answer_text=ocr_full.text or None,
                        ocr_provider=ocr_full.provider,
                        ocr_confidence=ocr_full.confidence_avg,
                        grading_confidence=grade.grading_confidence,
                        requires_manual_review=review,
                        manual_review_reason=mr_reason,
                        criteria_met_json=_annotate_json(grade.criteria_met),
                        criteria_missing_json=_annotate_json(grade.criteria_missing),
                        source_page_number=page_idx + 1,
                        source_question_number=eq.question_number,
                    )
                    db.add(qs)

                db.commit()

        # --- Consolidar status por StudentResult ---
        sr_rows = db.query(StudentResult).filter(StudentResult.batch_id == batch.id).all()
        sr_ids = [sr.id for sr in sr_rows]

        for sr_id in sr_ids:
            sr_row = db.query(StudentResult).filter(StudentResult.id == sr_id).first()
            if not sr_row:
                continue
            scores_list = db.query(QuestionScore).filter(QuestionScore.student_result_id == sr_id).all()

            sr_row.total_score = _effective_total(scores_list)
            any_manual = any(s.requires_manual_review for s in scores_list)
            if any_manual:
                sr_row.status = ResultStatus.GRADED
            else:
                sr_row.status = ResultStatus.AUTO_APPROVED
                for s in scores_list:
                    if s.final_score is None and not s.requires_manual_review:
                        s.final_score = s.ai_score
            db.commit()

        any_batch_manual = (
            db.query(QuestionScore)
            .join(StudentResult)
            .filter(
                StudentResult.batch_id == batch.id,
                QuestionScore.requires_manual_review.is_(True),
            )
            .first()
            is not None
        )

        batch.status = BatchStatus.REVIEW_PENDING if any_batch_manual else BatchStatus.DONE
        db.commit()

        logger.info("[batch=%s] Pipeline concluído.", batch_id)

    except Exception:
        db.rollback()
        try:
            batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
            if batch:
                batch.status = BatchStatus.FAILED
                db.commit()
        except Exception:
            db.rollback()
        logger.exception("[batch=%s] Erro inesperado.", batch_id)
    finally:
        db.close()
