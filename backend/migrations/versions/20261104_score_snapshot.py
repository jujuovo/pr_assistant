"""add reproducible student score snapshots

Revision ID: 20261104_score_snapshot
Revises: 20261104_score_entry
"""

from alembic import op
import sqlalchemy as sa


revision = "20261104_score_snapshot"
down_revision = "20261104_score_entry"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "student_score_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.String(length=20), nullable=False),
        sa.Column("faculty_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("academic_base_score", sa.Numeric(12, 4), nullable=False),
        sa.Column("academic_weight", sa.Numeric(8, 4), nullable=False),
        sa.Column("specialty_score", sa.Numeric(12, 4), nullable=False),
        sa.Column("performance_score", sa.Numeric(12, 4), nullable=False),
        sa.Column("comprehensive_score", sa.Numeric(12, 4), nullable=False),
        sa.Column("input_digest", sa.String(length=64), nullable=False),
        sa.Column("rule_version_ids", sa.JSON(), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status in ('current','superseded')", name="ck_student_score_snapshot_status"
        ),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculty.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["student.student_id"]),
        sa.UniqueConstraint(
            "student_id", "year", "input_digest", name="uq_student_score_snapshot_input"
        ),
        sa.UniqueConstraint(
            "student_id", "year", "version", name="uq_student_score_snapshot_version"
        ),
    )


def downgrade():
    op.drop_table("student_score_snapshot")

