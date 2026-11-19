"""add ranking batches and entries

Revision ID: 20261104_ranking_models
Revises: 20261104_score_snapshot
"""

from alembic import op
import sqlalchemy as sa


revision = "20261104_ranking_models"
down_revision = "20261104_score_snapshot"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ranking_batch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("faculty_id", sa.Integer(), nullable=False),
        sa.Column("major_id", sa.Integer(), nullable=True),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_definition", sa.JSON(), nullable=False),
        sa.Column("cutoff_at", sa.DateTime(), nullable=False),
        sa.Column("rule_version_ids", sa.JSON(), nullable=False),
        sa.Column("score_precision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("input_digest", sa.String(length=64), nullable=False),
        sa.Column("predecessor_batch_id", sa.Integer(), nullable=True),
        sa.Column("stale_reason", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("frozen_by", sa.Integer(), nullable=True),
        sa.Column("frozen_at", sa.DateTime(), nullable=True),
        sa.Column("published_by", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("withdrawn_by", sa.Integer(), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
        sa.Column("withdrawal_reason", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "score_precision >= 0 and score_precision <= 8",
            name="ck_ranking_batch_precision",
        ),
        sa.CheckConstraint(
            "status in ('draft','stale','frozen','published','withdrawn')",
            name="ck_ranking_batch_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculty.id"]),
        sa.ForeignKeyConstraint(["frozen_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["major_id"], ["major.id"]),
        sa.ForeignKeyConstraint(["predecessor_batch_id"], ["ranking_batch.id"]),
        sa.ForeignKeyConstraint(["published_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["withdrawn_by"], ["user.id"]),
        sa.UniqueConstraint(
            "year", "faculty_id", "scope_type", "input_digest",
            name="uq_ranking_batch_scope_input",
        ),
    )
    op.create_table(
        "ranking_entry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.String(length=20), nullable=False),
        sa.Column("score_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("frozen_score", sa.Numeric(12, 4), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("exclusion_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("display_order > 0", name="ck_ranking_entry_order"),
        sa.CheckConstraint("rank is null or rank > 0", name="ck_ranking_entry_rank"),
        sa.ForeignKeyConstraint(["batch_id"], ["ranking_batch.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["score_snapshot_id"], ["student_score_snapshot.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["student.student_id"]),
        sa.UniqueConstraint("batch_id", "display_order", name="uq_ranking_entry_order"),
        sa.UniqueConstraint("batch_id", "student_id", name="uq_ranking_entry_student"),
    )


def downgrade():
    op.drop_table("ranking_entry")
    op.drop_table("ranking_batch")

