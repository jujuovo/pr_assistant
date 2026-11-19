"""Persist merged multi-category OCR jobs without changing score or application tables."""
from alembic import op
import sqlalchemy as sa

revision = "20261118_ocr_jobs"
down_revision = "20261013_materials"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ocr_job",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("faculty_id", sa.Integer(), sa.ForeignKey("faculty.id"), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("report", sa.JSON()), sa.Column("error", sa.Text()),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.String(36)), sa.Column("lease_until", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_ocr_job_queue", "ocr_job", ["status", "lease_until"])


def downgrade():
    op.drop_index("ix_ocr_job_queue", table_name="ocr_job")
    op.drop_table("ocr_job")
