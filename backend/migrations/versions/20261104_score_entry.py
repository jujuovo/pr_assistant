"""add auditable score entries

Revision ID: 20261104_score_entry
Revises: 20261104_rule_version
"""

from alembic import op
import sqlalchemy as sa


revision = "20261104_score_entry"
down_revision = "20261104_rule_version"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "score_entry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.String(length=20), nullable=False),
        sa.Column("faculty_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("score_group", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("material_record_id", sa.Integer(), nullable=True),
        sa.Column("rule_version_id", sa.Integer(), nullable=False),
        sa.Column("raw_score", sa.Numeric(12, 4), nullable=False),
        sa.Column("adjusted_score", sa.Numeric(12, 4), nullable=False),
        sa.Column("effective_score", sa.Numeric(12, 4), nullable=False),
        sa.Column("included", sa.Boolean(), nullable=False),
        sa.Column("exclusion_reason", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("invalidated_reason", sa.String(length=500), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("source_revision > 0", name="ck_score_entry_source_revision_positive"),
        sa.CheckConstraint("status in ('active','invalidated')", name="ck_score_entry_status"),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculty.id"]),
        sa.ForeignKeyConstraint(["material_record_id"], ["material_record.id"]),
        sa.ForeignKeyConstraint(["rule_version_id"], ["rule_version.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["student.student_id"]),
        sa.UniqueConstraint("idempotency_key", name="uq_score_entry_idempotency_key"),
        sa.UniqueConstraint(
            "source_type", "source_id", "source_revision", "rule_version_id",
            name="uq_score_entry_source_revision_rule",
        ),
    )


def downgrade():
    op.drop_table("score_entry")

