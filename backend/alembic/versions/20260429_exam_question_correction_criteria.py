"""Critérios de correção por questão

Revision ID: 20260429_exam_question_criteria
Revises: 20260429_review_traceability
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20260429_exam_question_criteria"
down_revision = "20260429_review_traceability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {col["name"] for col in inspector.get_columns("exam_questions")}
    if "correction_criteria" not in cols:
        op.add_column("exam_questions", sa.Column("correction_criteria", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {col["name"] for col in inspector.get_columns("exam_questions")}
    if "correction_criteria" in cols:
        op.drop_column("exam_questions", "correction_criteria")
