"""Campos dedicados para vinculação aluno-página no visual_exam_answers

Revision ID: 20260428_ve_answer_identity
Revises: 20260428_visual_exam_openrouter
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "20260428_ve_answer_identity"
down_revision = "20260428_visual_exam_openrouter"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("visual_exam_answers", sa.Column("detected_student_code", sa.String(), nullable=True))
    op.add_column("visual_exam_answers", sa.Column("ocr_confidence", sa.Float(), nullable=True))
    op.add_column("visual_exam_answers", sa.Column("image_region", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("visual_exam_answers", "image_region")
    op.drop_column("visual_exam_answers", "ocr_confidence")
    op.drop_column("visual_exam_answers", "detected_student_code")
