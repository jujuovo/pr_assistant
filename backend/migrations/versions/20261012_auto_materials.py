"""Add volunteer automation without rewriting existing application records."""
from alembic import op
import sqlalchemy as sa

revision = "20261012_auto"
down_revision = "6be17e8f4f8a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("automation_policy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("faculty_id", sa.Integer(), sa.ForeignKey("faculty.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False), sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.UniqueConstraint("faculty_id", "year", name="uq_auto_policy_year"))
    op.create_table("automation_batch",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.String(20), sa.ForeignKey("student.student_id"), nullable=False),
        sa.Column("faculty_id", sa.Integer(), sa.ForeignKey("faculty.id"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False), sa.Column("material_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("application.id"), unique=True),
        sa.Column("policy_snapshot", sa.JSON()), sa.Column("score_snapshot", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime()), sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text()), sa.Column("version", sa.Integer(), nullable=False))
    op.create_table("automation_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("automation_batch.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False), sa.Column("stored_name", sa.String(80)),
        sa.Column("sha256", sa.String(64), nullable=False), sa.Column("status", sa.String(24), nullable=False),
        sa.Column("duplicate_of", sa.Integer(), sa.ForeignKey("automation_item.id")),
        sa.Column("report", sa.JSON()), sa.Column("raw_ocr", sa.JSON()),
        sa.Column("claimed_hours", sa.Numeric(12, 4)), sa.Column("confirmed_hours", sa.Numeric(12, 4)),
        sa.Column("activity_dates", sa.JSON()), sa.Column("submitted", sa.Boolean(), nullable=False),
        sa.Column("review_comment", sa.Text()), sa.Column("error", sa.Text()))
    op.create_table("automation_fingerprint",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.String(20), sa.ForeignKey("student.student_id"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False), sa.Column("value", sa.String(64), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("automation_item.id"), nullable=False),
        sa.UniqueConstraint("student_id", "kind", "value", name="uq_auto_fingerprint"))
    op.create_table("automation_review",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("automation_batch.id"), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("details", sa.JSON(), nullable=False))
    op.create_index("ix_auto_queue", "automation_batch", ["status", "lease_until"])
    op.create_index("ix_auto_student_year", "automation_batch", ["student_id", "year", "status"])
    op.create_index("ix_auto_items_batch", "automation_item", ["batch_id"])


def downgrade():
    op.drop_table("automation_review")
    op.drop_table("automation_fingerprint")
    op.drop_table("automation_item")
    op.drop_table("automation_batch")
    op.drop_table("automation_policy")
