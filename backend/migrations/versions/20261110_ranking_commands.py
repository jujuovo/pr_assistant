"""add unified ranking command ledger

Revision ID: 20261110_ranking_commands
Revises: 20261110_ranking_correction
"""
from alembic import op
import sqlalchemy as sa


revision = "20261110_ranking_commands"
down_revision = "20261110_ranking_correction"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ranking_command",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("ranking_batch.id"), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("ranking_command")
