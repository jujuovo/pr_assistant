"""add audited structured material migration batches

Revision ID: 20261108_structured_migration
Revises: 20261108_material_corrections
"""
from alembic import op
import sqlalchemy as sa

revision = "20261108_structured_migration"
down_revision = "20261108_material_corrections"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "structured_material_migration_batch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_key", sa.String(128), nullable=False, unique=True),
        sa.Column("backup_reference", sa.String(500), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "structured_material_migration_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("material_record_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["structured_material_migration_batch.id"]),
        sa.ForeignKeyConstraint(["material_record_id"], ["material_record.id"]),
        sa.UniqueConstraint("batch_id", "material_record_id",
                            name="uq_structured_migration_item_material"),
    )


def downgrade():
    op.drop_table("structured_material_migration_item")
    op.drop_table("structured_material_migration_batch")
