"""Preserve immutable OCR-to-material confirmation snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "20261118_ocr_links"
down_revision = "20261118_ocr_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("ocr_material_link",
        sa.Column("job_id", sa.String(36), sa.ForeignKey("ocr_job.id"), primary_key=True),
        sa.Column("material_record_id", sa.Integer(), sa.ForeignKey("material_record.id"), nullable=False),
        sa.Column("suggestions", sa.JSON(), nullable=False),
        sa.Column("confirmed_snapshot", sa.JSON(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_ocr_material_record", "ocr_material_link", ["material_record_id"])


def downgrade():
    op.drop_table("ocr_material_link")
