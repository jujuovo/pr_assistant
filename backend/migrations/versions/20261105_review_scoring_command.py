"""add unified review/scoring command idempotency records

Revision ID: 20261105_review_command
Revises: 20261105_cycle_policy
"""

from alembic import op
import sqlalchemy as sa


revision = "20261105_review_command"
down_revision = "20261105_cycle_policy"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "review_scoring_command",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("source_version > 0", name="ck_review_scoring_source_version"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.UniqueConstraint(
            "source_type", "source_id", "idempotency_key",
            name="uq_review_scoring_source_key",
        ),
    )


def downgrade():
    op.drop_table("review_scoring_command")
