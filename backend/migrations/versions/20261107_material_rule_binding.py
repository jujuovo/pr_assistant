"""bind submitted materials to immutable structured rule versions

Revision ID: 20261107_material_rule_binding
Revises: 20261106_structured_rules
"""
from alembic import op
import sqlalchemy as sa

revision = "20261107_material_rule_binding"
down_revision = "20261106_structured_rules"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("material_record") as batch:
        batch.add_column(sa.Column("rule_version_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_material_record_rule_version", "rule_version",
            ["rule_version_id"], ["id"],
        )
        batch.create_index(
            "ix_material_rule_state", ["status", "rule_version_id"], unique=False
        )


def downgrade():
    with op.batch_alter_table("material_record") as batch:
        batch.drop_index("ix_material_rule_state")
        batch.drop_constraint("fk_material_record_rule_version", type_="foreignkey")
        batch.drop_column("rule_version_id")
