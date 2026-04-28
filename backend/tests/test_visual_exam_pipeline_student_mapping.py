from app.services.visual_exam_pipeline import analyze_discursive_exam_pdf


def test_student_mapping_uses_detected_header_not_page_order(monkeypatch, tmp_path):
    pdf_path = tmp_path / "prova.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(
        "app.services.visual_exam_pipeline.render_pdf_to_images",
        lambda *_args, **_kwargs: [f"page-{idx}" for idx in range(1, 9)],
    )
    monkeypatch.setattr(
        "app.services.visual_exam_pipeline.normalize_page_image",
        lambda image: image,
    )
    monkeypatch.setattr(
        "app.services.visual_exam_pipeline.maybe_crop_answer_regions",
        lambda _image: {"regions": []},
    )
    monkeypatch.setattr(
        "app.services.visual_exam_pipeline.grade_discursive_answer",
        lambda question, _rubric, _answer, reading_confidence="media": {
            "question_number": int(question.get("number") or 0),
            "score": 0.0,
            "max_score": 1.0,
            "verdict": "parcial",
            "justification": "ok",
            "detected_concepts": [],
            "missing_concepts": [],
            "needs_human_review": reading_confidence == "baixa",
            "review_reason": "",
            "model_used": "mock-model",
            "fallback_used": False,
        },
    )

    def fake_extract(_image_path, page_number=None, context=None):
        if page_number == 1:
            return {
                "student": {
                    "name": "ALUNO 09",
                    "registration": "24102MED009",
                    "class": "T1",
                    "student_code": "009",
                },
                "physical_page": 1,
                "questions": [
                    {
                        "number": 1,
                        "prompt_detected": "Q1",
                        "answer_transcription": "Resposta do aluno 09",
                        "reading_confidence": "alta",
                        "ocr_confidence": 0.93,
                        "reading_notes": "",
                        "has_answer": True,
                        "image_region": {"x": 1, "y": 2, "w": 3, "h": 4},
                    }
                ],
                "model_used": "vision-mock",
                "fallback_used": False,
            }
        if page_number == 8:
            return {
                "student": {
                    "name": "ALUNO 01",
                    "registration": "24102MED001",
                    "class": "T1",
                    "student_code": "001",
                },
                "physical_page": 8,
                "questions": [
                    {
                        "number": 1,
                        "prompt_detected": "Q1",
                        "answer_transcription": "Eita, essa me pegou...",
                        "reading_confidence": "media",
                        "ocr_confidence": 0.88,
                        "reading_notes": "",
                        "has_answer": True,
                        "image_region": {"q": 1},
                    },
                    {
                        "number": 2,
                        "prompt_detected": "Q2",
                        "answer_transcription": "Não faço ideia...",
                        "reading_confidence": "alta",
                        "ocr_confidence": 0.95,
                        "reading_notes": "",
                        "has_answer": True,
                        "image_region": {"q": 2},
                    },
                    {
                        "number": 3,
                        "prompt_detected": "Q3",
                        "answer_transcription": "Tem ácido lático e sensação de queimação muscular.",
                        "reading_confidence": "alta",
                        "ocr_confidence": 0.96,
                        "reading_notes": "",
                        "has_answer": True,
                        "image_region": {"q": 3},
                    },
                ],
                "model_used": "vision-mock",
                "fallback_used": False,
            }
        return {
            "student": {
                "name": f"ALUNO X{page_number}",
                "registration": f"REG{page_number:03d}",
                "class": "T1",
                "student_code": f"{page_number:03d}",
            },
            "physical_page": page_number,
            "questions": [],
            "model_used": "vision-mock",
            "fallback_used": False,
        }

    monkeypatch.setattr(
        "app.services.visual_exam_pipeline.extract_answers_from_page_image",
        fake_extract,
    )

    result = analyze_discursive_exam_pdf(str(pdf_path), rubric={"questions": []}, options={})
    assert result["status"] == "success"

    by_page = {entry["physical_page"]: entry for entry in result["students"]}
    assert by_page[1]["detected_student_code"] == "009"
    assert by_page[1]["detected_student_name"] == "ALUNO 09"
    assert by_page[8]["detected_student_code"] == "001"
    assert by_page[8]["detected_registration"] == "24102MED001"

    aluno_01 = by_page[8]
    answers = {q["question_number"]: q["extracted_answer"] for q in aluno_01["questions"]}
    assert answers[1].startswith("Eita, essa me pegou")
    assert answers[2].startswith("Não faço ideia")
    assert "ácido lático" in answers[3]
    assert "queimação" in answers[3]

    aluno_09_answers = {q["question_number"]: q["extracted_answer"] for q in by_page[1]["questions"]}
    assert answers[1] != aluno_09_answers[1]
