"""Item 13 do docs/HTR_PLANO_EXECUCAO.md: o ciclo de rotulagem.

Toda vez que o professor corrige uma transcricao na revisao, ele produz sem
esforco adicional o dado mais caro deste dominio: um par
(recorte, o que o modelo leu, o que esta escrito de fato). Hoje essa informacao
era sobrescrita e sumia.
"""

from uuid import uuid4

import pytest

from app.services.htr_labeling import export_dataset, record_review


class _FakeScore:
    """QuestionScore o bastante para o servico, sem tocar no banco."""

    def __init__(self, *, crop="local:crops/x/p001_q001.png", model_text="actina e miosina"):
        self.id = uuid4()
        self.answer_crop_path = crop
        self.extracted_answer_text = model_text
        self.source_question_number = 1
        self.source_page_number = 3
        self.transcription_confidence = 0.91
        self.ocr_provider = "openrouter"


class _FakeDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)


@pytest.fixture
def db():
    return _FakeDB()


# --- gravacao -----------------------------------------------------------------


def test_correction_is_recorded_as_a_labeled_pair(db):
    label = record_review(
        db, question_score=_FakeScore(model_text="octina e miosino"), human_transcription="actina e miosina"
    )

    assert label is not None
    assert db.added == [label]
    assert label.model_transcription == "octina e miosino"
    assert label.human_transcription == "actina e miosina"
    assert label.was_correct is False
    assert label.character_error_rate > 0


def test_confirmation_is_recorded_too(db):
    """So gravar correcoes enviesaria o conjunto: todo exemplo seria um erro."""
    label = record_review(
        db, question_score=_FakeScore(model_text="actina e miosina"), human_transcription="actina e miosina"
    )

    assert label.was_correct is True
    assert label.character_error_rate == 0.0


def test_confirmation_ignores_whitespace_and_case():
    db = _FakeDB()
    label = record_review(
        db,
        question_score=_FakeScore(model_text="Actina  e\nmiosina"),
        human_transcription="actina e miosina",
    )

    assert label.was_correct is True


def test_confirmed_empty_box_is_a_valid_label(db):
    """E justamente o caso que mede alucinacao."""
    label = record_review(db, question_score=_FakeScore(model_text=""), human_transcription="")

    assert label is not None
    assert label.was_correct is True
    assert label.human_transcription == ""


def test_hallucination_is_recorded_as_a_correction(db):
    """Modelo escreveu onde nao havia nada: o par mais valioso do conjunto."""
    label = record_review(
        db, question_score=_FakeScore(model_text="inventou uma resposta"), human_transcription=""
    )

    assert label.was_correct is False
    assert label.character_error_rate == pytest.approx(1.0)


def test_no_crop_means_no_label(db):
    """Rotulo sem recorte e uma linha de texto sem contexto: nao e auditavel."""
    assert record_review(db, question_score=_FakeScore(crop=None), human_transcription="actina") is None
    assert db.added == []


def test_metadata_is_carried_for_later_analysis(db):
    exam_id, student_id, reviewer_id = uuid4(), uuid4(), uuid4()

    label = record_review(
        db,
        question_score=_FakeScore(),
        human_transcription="actina e miosina",
        exam_id=exam_id,
        student_id=student_id,
        reviewer_id=reviewer_id,
        vision_model="qwen/qwen2.5-vl-72b-instruct",
    )

    assert label.exam_id == exam_id
    assert label.student_id == student_id
    assert label.reviewer_id == reviewer_id
    assert label.vision_model == "qwen/qwen2.5-vl-72b-instruct"
    assert label.question_number == 1
    assert label.page_number == 3


@pytest.mark.parametrize(
    "numeric,expected",
    [(0.95, "alta"), (0.70, "media"), (0.30, "baixa"), (None, None)],
)
def test_numeric_confidence_becomes_a_label(numeric, expected):
    db = _FakeDB()
    score = _FakeScore()
    score.transcription_confidence = numeric

    label = record_review(db, question_score=score, human_transcription="actina")

    assert label.reading_confidence == expected


def test_service_does_not_commit(db):
    """Quem chama decide o limite da transacao, que inclui a nota."""
    record_review(db, question_score=_FakeScore(), human_transcription="actina")

    assert not hasattr(db, "committed")


# --- exportacao ---------------------------------------------------------------


class _Label:
    def __init__(self, human, model="x", correct=False, cer=0.5, question=1):
        self.answer_crop_path = "local:crops/a/p001_q001.png"
        self.human_transcription = human
        self.model_transcription = model
        self.was_correct = correct
        self.character_error_rate = cer
        self.question_number = question


class _QueryDB:
    def __init__(self, rows):
        self.rows = rows

    def query(self, _model):
        return self

    def filter(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def limit(self, n):
        self.rows = self.rows[:n]
        return self

    def all(self):
        return self.rows


def test_export_uses_the_eval_harness_format():
    db = _QueryDB([_Label("actina e miosina deslizam")])

    rows = export_dataset(db)

    assert set(rows[0]) >= {"crop", "reference", "strata"}
    assert rows[0]["reference"] == "actina e miosina deslizam"


def test_export_marks_corrected_and_confirmed_separately():
    db = _QueryDB([_Label("actina", correct=True), _Label("miosina", correct=False)])

    rows = export_dataset(db)

    assert "confirmada" in rows[0]["strata"]
    assert "corrigida" in rows[1]["strata"]


def test_export_infers_the_strata_it_can():
    db = _QueryDB([_Label(""), _Label("nao sei"), _Label("uma resposta bem mais longa que tres palavras")])

    rows = export_dataset(db)

    assert "vazia" in rows[0]["strata"]
    assert "curta" in rows[1]["strata"]
    assert "curta" not in rows[2]["strata"]


def test_export_respects_the_limit():
    db = _QueryDB([_Label(f"resposta {i}") for i in range(10)])

    assert len(export_dataset(db, limit=3)) == 3
