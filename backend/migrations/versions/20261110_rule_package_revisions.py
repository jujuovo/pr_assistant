"""add immutable draft revision snapshots

Revision ID: 20261110_rule_package_revisions
Revises: 20261110_rule_package_commands
"""
from alembic import op
import sqlalchemy as sa


revision = "20261110_rule_package_revisions"
down_revision = "20261110_rule_package_commands"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "competition_rule_package_revision",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_id", sa.Integer(),
                  sa.ForeignKey("competition_rule_package.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("package_id", "revision",
                            name="uq_competition_package_revision"),
        sa.CheckConstraint("revision > 0", name="ck_competition_package_revision_positive"),
    )


def downgrade():
    op.drop_table("competition_rule_package_revision")
