"""Tabelas de auditoria para leitura visual via OpenRouter

Revision ID: 20260428_visual_exam_openrouter
Revises: 20260428_unique_question_scores
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260428_visual_exam_openrouter"
down_revision = "20260428_unique_question_scores"
branch_labels = None
depends_on = None


visual_exam_run_status = postgresql.ENUM(
    "PROCESSING",
    "SUCCESS",
    "FAILED",
    name="visualexamrunstatus",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'visualexamrunstatus'
            ) THEN
                CREATE TYPE visualexamrunstatus AS ENUM ('PROCESSING', 'SUCCESS', 'FAILED');
            END IF;
        END
        $$;
        """
    )

    op.create_table(
        "visual_exam_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("status", visual_exam_run_status, nullable=False),
        sa.Column("pages_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vision_model_used", sa.String(), nullable=True),
        sa.Column("text_model_used", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "visual_exam_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_name", sa.String(), nullable=True),
        sa.Column("registration", sa.String(), nullable=True),
        sa.Column("class_name", sa.String(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("prompt_detected", sa.Text(), nullable=True),
        sa.Column("answer_transcription", sa.Text(), nullable=True),
        sa.Column("reading_confidence", sa.String(), nullable=True),
        sa.Column("reading_notes", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("max_score", sa.Float(), nullable=True),
        sa.Column("verdict", sa.String(), nullable=True),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("detected_concepts_json", sa.Text(), nullable=True),
        sa.Column("missing_concepts_json", sa.Text(), nullable=True),
        sa.Column("needs_human_review", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("raw_vision_json", sa.Text(), nullable=True),
        sa.Column("raw_grading_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["visual_exam_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_visual_exam_answers_run_id", "visual_exam_answers", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_visual_exam_answers_run_id", table_name="visual_exam_answers")
    op.drop_table("visual_exam_answers")
    op.drop_table("visual_exam_runs")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'visualexamrunstatus'
            ) THEN
                DROP TYPE visualexamrunstatus;
            END IF;
        END
        $$;
        """
    )
