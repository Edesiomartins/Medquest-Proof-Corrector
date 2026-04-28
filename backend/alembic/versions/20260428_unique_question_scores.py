"""Impede nota duplicada por resultado e questão

Revision ID: 20260428_unique_question_scores
Revises: 20260427_auto_grading
Create Date: 2026-04-28
"""

from alembic import op


revision = "20260428_unique_question_scores"
down_revision = "20260427_auto_grading"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_question_scores_result_question",
        "question_scores",
        ["student_result_id", "question_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_question_scores_result_question",
        "question_scores",
        type_="unique",
    )
