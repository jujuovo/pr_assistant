"""add separated material evidence term snapshots

Revision ID: 20261106_structured_terms
Revises: 20261106_backfill_evidence
"""
from alembic import op
import sqlalchemy as sa

revision = "20261106_structured_terms"
down_revision = "20261106_backfill_evidence"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("material_record") as batch:
        batch.add_column(sa.Column("ocr_raw_terms", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("confirmed_terms", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("normalized_terms", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("normalization_version", sa.String(32), nullable=True))


def downgrade():
    with op.batch_alter_table("material_record") as batch:
        batch.drop_column("normalization_version")
        batch.drop_column("normalized_terms")
        batch.drop_column("confirmed_terms")
        batch.drop_column("ocr_raw_terms")
