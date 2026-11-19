"""add material review command idempotency records

Revision ID: 20261104_review_command
Revises: 20261104_ranking_models
"""

from alembic import op
import sqlalchemy as sa


revision = "20261104_review_command"
down_revision = "20261104_ranking_models"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "material_review_command",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["record_id"], ["material_record.id"]),
        sa.UniqueConstraint(
            "record_id", "idempotency_key", name="uq_material_review_command_key"
        ),
    )


def downgrade():
    op.drop_table("material_review_command")
