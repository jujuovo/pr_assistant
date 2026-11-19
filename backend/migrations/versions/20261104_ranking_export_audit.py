"""add ranking export audit

Revision ID: 20261104_rank_export
Revises: 20261104_snapshot_caps
"""
from alembic import op
import sqlalchemy as sa

revision="20261104_rank_export"
down_revision="20261104_snapshot_caps"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("ranking_export_audit",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("batch_id",sa.Integer(),nullable=False),
        sa.Column("actor_id",sa.Integer(),nullable=False),
        sa.Column("entry_count",sa.Integer(),nullable=False),
        sa.Column("purpose",sa.String(length=500),nullable=False),
        sa.Column("created_at",sa.DateTime(),nullable=False),
        sa.ForeignKeyConstraint(["batch_id"],["ranking_batch.id"]),
        sa.ForeignKeyConstraint(["actor_id"],["user.id"]))

def downgrade():
    op.drop_table("ranking_export_audit")
