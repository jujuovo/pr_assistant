"""Persist standalone certificate OCR tasks and reports."""
from alembic import op
import sqlalchemy as sa

revision = "20261013_certificate"
down_revision = "20261012_auto"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("certificate_assessment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("application.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("project_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("claims", sa.JSON(), nullable=False), sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("artifact_key", sa.String(36), nullable=False), sa.Column("report", sa.JSON()),
        sa.Column("error", sa.Text()), sa.Column("lease_token", sa.String(36)), sa.Column("lease_until", sa.DateTime()),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_certificate_queue", "certificate_assessment", ["status", "lease_until"])


def downgrade():
    op.drop_table("certificate_assessment")
