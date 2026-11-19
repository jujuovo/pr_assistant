"""add recommendation cycle policy versions

Revision ID: 20261105_cycle_policy
Revises: 20261104_backfill
"""

from alembic import op
import sqlalchemy as sa


revision = "20261105_cycle_policy"
down_revision = "20261104_backfill"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recommendation_cycle_policy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cycle_code", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(50), nullable=False),
        sa.Column("eligible_award_start_date", sa.Date(), nullable=False),
        sa.Column("eligible_award_end_date", sa.Date(), nullable=False),
        sa.Column("boundary", sa.String(20), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("active_marker", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("activated_by", sa.Integer(), nullable=True),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("cycle_code >= 2000 and cycle_code <= 2100", name="ck_cycle_policy_code"),
        sa.CheckConstraint("eligible_award_end_date >= eligible_award_start_date", name="ck_cycle_policy_dates"),
        sa.CheckConstraint("boundary = 'inclusive'", name="ck_cycle_policy_boundary"),
        sa.CheckConstraint("status in ('draft','active','retired')", name="ck_cycle_policy_status"),
        sa.CheckConstraint("active_marker is null or active_marker = 1", name="ck_cycle_policy_active_marker"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["activated_by"], ["user.id"]),
        sa.UniqueConstraint("active_marker", name="uq_cycle_policy_active_marker"),
        sa.UniqueConstraint("cycle_code", "version", name="uq_cycle_policy_version"),
        sa.UniqueConstraint("cycle_code", "digest", name="uq_cycle_policy_digest"),
    )
    with op.batch_alter_table("system_settings") as batch:
        batch.add_column(sa.Column("active_cycle_policy_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_system_settings_active_cycle_policy",
            "recommendation_cycle_policy",
            ["active_cycle_policy_id"],
            ["id"],
        )
    with op.batch_alter_table("application") as batch:
        batch.add_column(sa.Column("cycle_code", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("cycle_policy_version_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_application_cycle_policy",
            "recommendation_cycle_policy",
            ["cycle_policy_version_id"],
            ["id"],
        )
    with op.batch_alter_table("material_record") as batch:
        batch.add_column(sa.Column("cycle_policy_version_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_material_record_cycle_policy",
            "recommendation_cycle_policy",
            ["cycle_policy_version_id"],
            ["id"],
        )
    with op.batch_alter_table("score_entry") as batch:
        batch.add_column(sa.Column("cycle_policy_version_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_score_entry_cycle_policy",
            "recommendation_cycle_policy",
            ["cycle_policy_version_id"],
            ["id"],
        )
    with op.batch_alter_table("student_score_snapshot") as batch:
        batch.add_column(
            sa.Column(
                "cycle_policy_version_ids",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            )
        )


def downgrade():
    with op.batch_alter_table("student_score_snapshot") as batch:
        batch.drop_column("cycle_policy_version_ids")
    with op.batch_alter_table("score_entry") as batch:
        batch.drop_constraint("fk_score_entry_cycle_policy", type_="foreignkey")
        batch.drop_column("cycle_policy_version_id")
    with op.batch_alter_table("material_record") as batch:
        batch.drop_constraint("fk_material_record_cycle_policy", type_="foreignkey")
        batch.drop_column("cycle_policy_version_id")
    with op.batch_alter_table("application") as batch:
        batch.drop_constraint("fk_application_cycle_policy", type_="foreignkey")
        batch.drop_column("cycle_policy_version_id")
        batch.drop_column("cycle_code")
    with op.batch_alter_table("system_settings") as batch:
        batch.drop_constraint("fk_system_settings_active_cycle_policy", type_="foreignkey")
        batch.drop_column("active_cycle_policy_id")
    op.drop_table("recommendation_cycle_policy")
