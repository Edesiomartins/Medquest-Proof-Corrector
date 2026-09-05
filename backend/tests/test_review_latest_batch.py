from uuid import uuid4

from app.api.v1.reviews import _latest_review_batch_id


class _Query:
    def __init__(self, row):
        self.row = row

    def order_by(self, *_args):
        return self

    def first(self):
        return self.row


class _DB:
    def __init__(self, row):
        self.row = row

    def query(self, *_args):
        return _Query(self.row)


def test_latest_review_batch_id_returns_most_recent_batch():
    batch_id = uuid4()

    assert _latest_review_batch_id(_DB((batch_id,))) == batch_id


def test_latest_review_batch_id_returns_none_without_batches():
    assert _latest_review_batch_id(_DB(None)) is None
