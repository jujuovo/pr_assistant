"""add append-only material correction lineage

Revision ID: 20261108_material_corrections
Revises: 20261107_material_rule_binding
"""
from alembic import op
import sqlalchemy as sa

revision = "20261108_material_corrections"
down_revision = "20261107_material_rule_binding"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("material_record") as batch:
        batch.add_column(sa.Column("supersedes_record_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("correction_sequence", sa.Integer(), nullable=False,
                                   server_default="0"))
        batch.create_foreign_key(
            "fk_material_record_supersedes", "material_record",
            ["supersedes_record_id"], ["id"],
        )
        batch.create_index("ix_material_correction_chain", ["supersedes_record_id"])


def downgrade():
    with op.batch_alter_table("material_record") as batch:
        batch.drop_index("ix_material_correction_chain")
        batch.drop_constraint("fk_material_record_supersedes", type_="foreignkey")
        batch.drop_column("correction_sequence")
        batch.drop_column("supersedes_record_id")
