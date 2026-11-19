"""add append-only score override audit

Revision ID: 20261105_score_override
Revises: 20261105_review_command
"""
from alembic import op
import sqlalchemy as sa

revision = "20261105_score_override"
down_revision = "20261105_review_command"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "score_override_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("score_entry_id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False),
        sa.Column("rule_version_id", sa.Integer(), nullable=False),
        sa.Column("automatic_score", sa.Numeric(12, 4), nullable=False),
        sa.Column("override_score", sa.Numeric(12, 4), nullable=False),
        sa.Column("difference", sa.Numeric(12, 4), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("override_score >= 0", name="ck_score_override_nonnegative"),
        sa.ForeignKeyConstraint(["score_entry_id"], ["score_entry.id"]),
        sa.ForeignKeyConstraint(["rule_version_id"], ["rule_version.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"]),
        sa.UniqueConstraint("score_entry_id", name="uq_score_override_entry"),
    )


def downgrade():
    op.drop_table("score_override_audit")
