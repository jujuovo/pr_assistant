"""legacy backfill batches

Revision ID: 20261104_backfill
Revises: 20261104_rank_export
"""
from alembic import op
import sqlalchemy as sa

revision = "20261104_backfill"
down_revision = "20261104_rank_export"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("legacy_backfill_batch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_key", sa.String(128), nullable=False, unique=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("backup_reference", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("processed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_table("legacy_backfill_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("legacy_backfill_batch.id"), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("application.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("batch_id", "application_id", name="uq_backfill_item_application"))

def downgrade():
    op.drop_table("legacy_backfill_item")
    op.drop_table("legacy_backfill_batch")
