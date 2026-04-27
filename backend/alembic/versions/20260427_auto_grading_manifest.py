"""layout manifest + question_scores metadados + AUTO_APPROVED

Revision ID: 20260427_auto_grading
Revises:
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_auto_grading"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'result_status'
                  AND e.enumlabel = 'AUTO_APPROVED'
            ) THEN
                ALTER TYPE result_status ADD VALUE 'AUTO_APPROVED';
            END IF;
        END $$;
        """
    )

    op.add_column("exams", sa.Column("layout_manifest_json", sa.Text(), nullable=True))

    op.add_column(
        "exam_questions",
        sa.Column("page_number", sa.Integer(), nullable=True),
    )
    op.add_column("exam_questions", sa.Column("box_x", sa.Float(), nullable=True))
    op.add_column("exam_questions", sa.Column("box_y", sa.Float(), nullable=True))
    op.add_column("exam_questions", sa.Column("box_w", sa.Float(), nullable=True))
    op.add_column("exam_questions", sa.Column("box_h", sa.Float(), nullable=True))

    op.add_column(
        "question_scores",
        sa.Column("extracted_answer_text", sa.Text(), nullable=True),
    )
    op.add_column("question_scores", sa.Column("ocr_provider", sa.String(), nullable=True))
    op.add_column("question_scores", sa.Column("ocr_confidence", sa.Float(), nullable=True))
    op.add_column("question_scores", sa.Column("grading_confidence", sa.Float(), nullable=True))
    op.add_column(
        "question_scores",
        sa.Column(
            "requires_manual_review",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column("question_scores", sa.Column("manual_review_reason", sa.Text(), nullable=True))
    op.add_column("question_scores", sa.Column("criteria_met_json", sa.Text(), nullable=True))
    op.add_column("question_scores", sa.Column("criteria_missing_json", sa.Text(), nullable=True))
    op.add_column("question_scores", sa.Column("source_page_number", sa.Integer(), nullable=True))
    op.add_column("question_scores", sa.Column("source_question_number", sa.Integer(), nullable=True))
    op.add_column("question_scores", sa.Column("crop_box_json", sa.Text(), nullable=True))

    op.alter_column("question_scores", "requires_manual_review", server_default=None)


def downgrade() -> None:
    op.drop_column("question_scores", "crop_box_json")
    op.drop_column("question_scores", "source_question_number")
    op.drop_column("question_scores", "source_page_number")
    op.drop_column("question_scores", "criteria_missing_json")
    op.drop_column("question_scores", "criteria_met_json")
    op.drop_column("question_scores", "manual_review_reason")
    op.drop_column("question_scores", "requires_manual_review")
    op.drop_column("question_scores", "grading_confidence")
    op.drop_column("question_scores", "ocr_confidence")
    op.drop_column("question_scores", "ocr_provider")
    op.drop_column("question_scores", "extracted_answer_text")

    op.drop_column("exam_questions", "box_h")
    op.drop_column("exam_questions", "box_w")
    op.drop_column("exam_questions", "box_y")
    op.drop_column("exam_questions", "box_x")
    op.drop_column("exam_questions", "page_number")

    op.drop_column("exams", "layout_manifest_json")

    # Não remove o valor do enum automaticamente no PostgreSQL (operação frágil).
