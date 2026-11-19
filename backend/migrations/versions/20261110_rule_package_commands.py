"""add competition rule package command ledger

Revision ID: 20261110_rule_package_commands
Revises: 20261110_rule_package_drafts
"""
from alembic import op
import sqlalchemy as sa


revision = "20261110_rule_package_commands"
down_revision = "20261110_rule_package_drafts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "competition_rule_package_command",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("command_type", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("competition_rule_package.id")),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("command_type", "idempotency_key",
                            name="uq_competition_package_command_key"),
    )


def downgrade():
    op.drop_table("competition_rule_package_command")
