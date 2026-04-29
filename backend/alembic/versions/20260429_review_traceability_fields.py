"""Campos de rastreabilidade para revisão humano-assistida

Revision ID: 20260429_review_traceability
Revises: 20260429_student_identity_source
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260429_review_traceability"
down_revision = "20260429_student_identity_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    sr_cols = {col["name"] for col in inspector.get_columns("student_results")}
    qs_cols = {col["name"] for col in inspector.get_columns("question_scores")}

    if "physical_page" not in sr_cols:
        op.add_column("student_results", sa.Column("physical_page", sa.Integer(), nullable=True))
    if "detected_student_name" not in sr_cols:
        op.add_column("student_results", sa.Column("detected_student_name", sa.String(length=255), nullable=True))
    if "detected_registration" not in sr_cols:
        op.add_column("student_results", sa.Column("detected_registration", sa.String(length=100), nullable=True))
    if "warnings_json" not in sr_cols:
        op.add_column(
            "student_results",
            sa.Column(
                "warnings_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )

    if "answer_crop_path" not in qs_cols:
        op.add_column("question_scores", sa.Column("answer_crop_path", sa.Text(), nullable=True))
    if "transcription_confidence" not in qs_cols:
        op.add_column("question_scores", sa.Column("transcription_confidence", sa.Float(), nullable=True))
    if "warnings_json" not in qs_cols:
        op.add_column(
            "question_scores",
            sa.Column(
                "warnings_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    sr_cols = {col["name"] for col in inspector.get_columns("student_results")}
    qs_cols = {col["name"] for col in inspector.get_columns("question_scores")}

    if "warnings_json" in qs_cols:
        op.drop_column("question_scores", "warnings_json")
    if "transcription_confidence" in qs_cols:
        op.drop_column("question_scores", "transcription_confidence")
    if "answer_crop_path" in qs_cols:
        op.drop_column("question_scores", "answer_crop_path")
    if "warnings_json" in sr_cols:
        op.drop_column("student_results", "warnings_json")
    if "detected_registration" in sr_cols:
        op.drop_column("student_results", "detected_registration")
    if "detected_student_name" in sr_cols:
        op.drop_column("student_results", "detected_student_name")
    if "physical_page" in sr_cols:
        op.drop_column("student_results", "physical_page")
