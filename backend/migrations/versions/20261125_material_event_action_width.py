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


def upgrade():
    op.alter_column(
        "material_event",
        "action",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade():
    connection = op.get_bind()
    longest_action = connection.execute(
        sa.text("SELECT MAX(length(action)) FROM material_event")
    ).scalar()
    if longest_action is not None and longest_action > 32:
        raise RuntimeError(
            "Cannot shrink material_event.action to 32 characters while longer audit events exist"
        )
    op.alter_column(
        "material_event",
        "action",
        existing_type=sa.String(length=64),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
