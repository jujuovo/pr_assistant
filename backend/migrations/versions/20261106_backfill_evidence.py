"""add explicit evidence to legacy backfill batches

Revision ID: 20261106_backfill_evidence
Revises: 20261105_score_override
"""
from alembic import op
import sqlalchemy as sa

revision = "20261106_backfill_evidence"
down_revision = "20261105_score_override"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("legacy_backfill_batch") as batch:
        batch.add_column(sa.Column("cycle_policy_version_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("evidence_manifest", sa.JSON(), nullable=True))
        batch.create_foreign_key("fk_backfill_cycle_policy", "recommendation_cycle_policy",
                                 ["cycle_policy_version_id"], ["id"])


def downgrade():
    with op.batch_alter_table("legacy_backfill_batch") as batch:
        batch.drop_constraint("fk_backfill_cycle_policy", type_="foreignkey")
        batch.drop_column("evidence_manifest")
        batch.drop_column("cycle_policy_version_id")
