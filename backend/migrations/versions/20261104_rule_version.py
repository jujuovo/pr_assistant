"""add immutable rule versions

Revision ID: 20261104_rule_version
Revises: 20261013_materials
"""

from alembic import op
import sqlalchemy as sa


revision = "20261104_rule_version"
down_revision = "20261013_materials"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rule_version",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("published_by", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["rule.id"]),
        sa.ForeignKeyConstraint(["published_by"], ["user.id"]),
        sa.UniqueConstraint("rule_id", "version", name="uq_rule_version_number"),
        sa.UniqueConstraint("rule_id", "digest", name="uq_rule_version_digest"),
    )


def downgrade():
    op.drop_table("rule_version")

