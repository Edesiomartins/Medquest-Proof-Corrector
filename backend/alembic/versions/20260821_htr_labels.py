"""Pares rotulados de leitura manuscrita (item 13 do plano de HTR)

Toda correção de transcrição feita na tela de revisão vira um par
`(recorte, leitura do modelo, leitura humana)`. Hoje essa informação é
sobrescrita e some; é o dado mais caro deste domínio, colhido de graça.

Revision ID: 20260821_htr_labels
Revises: 20260504_exam_is_practical
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260821_htr_labels"
down_revision = "20260504_exam_is_practical"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "htr_labels" not in inspector.get_table_names():
        op.create_table(
            "htr_labels",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "question_score_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("question_scores.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("exam_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("question_number", sa.Integer(), nullable=True),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("answer_crop_path", sa.Text(), nullable=False),
            sa.Column("model_transcription", sa.Text(), nullable=True),
            sa.Column("human_transcription", sa.Text(), nullable=False),
            sa.Column("character_error_rate", sa.Float(), nullable=True),
            sa.Column(
                "was_correct", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column("reading_confidence", sa.String(length=16), nullable=True),
            sa.Column("ocr_provider", sa.String(length=64), nullable=True),
            sa.Column("vision_model", sa.String(length=128), nullable=True),
            sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
        )
        # Exportar o conjunto de avaliação filtra por prova e ordena por data.
        op.create_index("ix_htr_labels_exam_id", "htr_labels", ["exam_id"])
        op.create_index("ix_htr_labels_created_at", "htr_labels", ["created_at"])

    qs_cols = {col["name"] for col in inspector.get_columns("question_scores")}
    if "transcription_edited_by_human" not in qs_cols:
        # Marca a transcrição que já passou por revisão humana, para não
        # sobrescrevê-la num reprocessamento do lote.
        op.add_column(
            "question_scores",
            sa.Column(
                "transcription_edited_by_human",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    qs_cols = {col["name"] for col in inspector.get_columns("question_scores")}
    if "transcription_edited_by_human" in qs_cols:
        op.drop_column("question_scores", "transcription_edited_by_human")

    if "htr_labels" in inspector.get_table_names():
        op.drop_index("ix_htr_labels_created_at", table_name="htr_labels")
        op.drop_index("ix_htr_labels_exam_id", table_name="htr_labels")
        op.drop_table("htr_labels")
