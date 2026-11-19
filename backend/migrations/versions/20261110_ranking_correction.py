"""add correction-required ranking state and event history

Revision ID: 20261110_ranking_correction
Revises: 20261110_rule_package_revisions
"""
from alembic import op
import sqlalchemy as sa


revision = "20261110_ranking_correction"
down_revision = "20261110_rule_package_revisions"
branch_labels = None
depends_on = None


OLD = "status in ('draft','stale','frozen','published','withdrawn')"
NEW = "status in ('draft','stale','frozen','correction_required','published','withdrawn')"


def upgrade():
    with op.batch_alter_table("ranking_batch") as batch:
        batch.drop_constraint("ck_ranking_batch_status", type_="check")
        batch.create_check_constraint("ck_ranking_batch_status", NEW)
        batch.add_column(sa.Column("correction_reason", sa.String(1000)))
        batch.add_column(sa.Column("correction_requested_by", sa.Integer()))
        batch.add_column(sa.Column("correction_requested_at", sa.DateTime()))
        batch.create_foreign_key("fk_ranking_correction_actor", "user",
                                 ["correction_requested_by"], ["id"])
    op.create_table(
        "ranking_state_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("ranking_batch.id"), nullable=False),
        sa.Column("from_status", sa.String(32)), sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(1000)), sa.Column("batch_version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("ranking_state_event")
    with op.batch_alter_table("ranking_batch") as batch:
        batch.drop_constraint("fk_ranking_correction_actor", type_="foreignkey")
        batch.drop_column("correction_requested_at")
        batch.drop_column("correction_requested_by")
        batch.drop_column("correction_reason")
        batch.drop_constraint("ck_ranking_batch_status", type_="check")
        batch.create_check_constraint("ck_ranking_batch_status", OLD)
