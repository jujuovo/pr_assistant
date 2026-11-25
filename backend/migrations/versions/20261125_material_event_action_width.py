"""Expand material event action names for descriptive audit events.

Revision ID: 20261125_event_action_width
Revises: 20261123_material_read_indexes
"""

from alembic import op
import sqlalchemy as sa


revision = "20261125_event_action_width"
down_revision = "20261123_material_read_indexes"
branch_labels = None
depends_on = None


def _resize_action(old_width, new_width):
    with op.batch_alter_table("material_event") as batch:
        batch.alter_column(
            "action",
            existing_type=sa.String(length=old_width),
            type_=sa.String(length=new_width),
            existing_nullable=False,
        )


def upgrade():
    _resize_action(32, 64)


def downgrade():
    connection = op.get_bind()
    longest_action = connection.execute(
        sa.text("SELECT MAX(length(action)) FROM material_event")
    ).scalar()
    if longest_action is not None and longest_action > 32:
        raise RuntimeError(
            "Cannot shrink material_event.action to 32 characters while longer audit events exist"
        )
    _resize_action(64, 32)
