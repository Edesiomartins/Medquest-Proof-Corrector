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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    current_columns = {col["name"] for col in inspector.get_columns("student_results")}
    if "identity_source" not in current_columns:
        op.add_column(
            "student_results",
            sa.Column("identity_source", sa.String(length=40), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    current_columns = {col["name"] for col in inspector.get_columns("student_results")}
    if "identity_source" in current_columns:
        op.drop_column("student_results", "identity_source")
