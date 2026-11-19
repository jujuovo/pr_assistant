"""add raw category totals to score snapshots

Revision ID: 20261104_snapshot_caps
Revises: 20261104_review_command
"""

from alembic import op
import sqlalchemy as sa


revision = "20261104_snapshot_caps"
down_revision = "20261104_review_command"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("student_score_snapshot") as batch:
        batch.add_column(sa.Column("specialty_raw_score", sa.Numeric(12, 4), nullable=False, server_default="0"))
        batch.add_column(sa.Column("performance_raw_score", sa.Numeric(12, 4), nullable=False, server_default="0"))


def downgrade():
    with op.batch_alter_table("student_score_snapshot") as batch:
        batch.drop_column("performance_raw_score")
        batch.drop_column("specialty_raw_score")
