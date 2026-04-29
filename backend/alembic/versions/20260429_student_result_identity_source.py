"""student_results.identity_source para auditoria de vínculo aluno-página

Revision ID: 20260429_student_identity_source
Revises: 20260428_ve_answer_identity
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20260429_student_identity_source"
down_revision = "20260428_ve_answer_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "student_results",
        sa.Column("identity_source", sa.String(length=40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("student_results", "identity_source")
