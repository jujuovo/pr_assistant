"""add ranking successor source summary

Revision ID: 20261110_ranking_source_summary
Revises: 20261110_ranking_commands
"""
from alembic import op
import sqlalchemy as sa


revision = "20261110_ranking_source_summary"
down_revision = "20261110_ranking_commands"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ranking_batch") as batch:
        batch.add_column(sa.Column("source_summary", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("ranking_batch") as batch:
        batch.drop_column("source_summary")
