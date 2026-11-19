"""add controlled score recalculation command ledger

Revision ID: 20261110_score_recalc
Revises: 20261110_ranking_source_summary
"""
from alembic import op
import sqlalchemy as sa

revision = "20261110_score_recalc"
down_revision = "20261110_ranking_source_summary"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "score_recalculation_command",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("preview_digest", sa.String(64), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

def downgrade():
    op.drop_table("score_recalculation_command")
