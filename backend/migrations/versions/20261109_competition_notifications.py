"""competition notification intents

Revision ID: 20261109_competition_notify
Revises: 20261109_competition_evidence
"""
from alembic import op
import sqlalchemy as sa

revision = "20261109_competition_notify"
down_revision = "20261109_competition_evidence"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("competition_notification_intent",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("intent_key", sa.String(160), nullable=False, unique=True),
        sa.Column("student_id", sa.String(20), sa.ForeignKey("student.student_id"), nullable=False),
        sa.Column("material_record_id", sa.Integer(), sa.ForeignKey("material_record.id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(1000)), sa.Column("sent_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status in ('pending','sent')", name="ck_competition_notification_status"),
        sa.CheckConstraint("attempts >= 0", name="ck_competition_notification_attempts"))


def downgrade():
    op.drop_table("competition_notification_intent")
