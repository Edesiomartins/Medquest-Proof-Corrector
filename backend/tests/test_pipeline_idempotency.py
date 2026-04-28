from uuid import uuid4

from app.models.grading import QuestionScore, StudentResult
from app.workers.pipeline import _clear_existing_batch_results


class _Query:
    def __init__(self, rows=None) -> None:
        self.rows = rows or []
        self.deleted = False

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self.rows

    def delete(self, synchronize_session=False):
        self.deleted = True
        return len(self.rows)


class _DB:
    def __init__(self, result_ids) -> None:
        self.student_query = _Query([(rid,) for rid in result_ids])
        self.score_query = _Query(result_ids)
        self.flush_called = False

    def query(self, model_attr):
        if model_attr is StudentResult.id:
            return self.student_query
        if model_attr is QuestionScore:
            return self.score_query
        if model_attr is StudentResult:
            return self.student_query
        raise AssertionError(f"Unexpected query target: {model_attr!r}")

    def flush(self):
        self.flush_called = True


def test_clear_existing_batch_results_deletes_scores_before_results():
    db = _DB([uuid4()])

    _clear_existing_batch_results(db, uuid4())

    assert db.score_query.deleted is True
    assert db.student_query.deleted is True
    assert db.flush_called is True


def test_clear_existing_batch_results_noops_without_results():
    db = _DB([])

    _clear_existing_batch_results(db, uuid4())

    assert db.score_query.deleted is False
    assert db.student_query.deleted is False
    assert db.flush_called is False
