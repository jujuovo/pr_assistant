"""Bind volunteer OCR jobs to immutable material versions and original attachments."""
from alembic import op
import sqlalchemy as sa
revision = "20261120_volunteer_ocr"
down_revision = "20261118_ocr_links"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ocr_job") as batch:
        batch.add_column(sa.Column("material_record_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("material_version", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("attachment_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_ocr_material", "material_record", ["material_record_id"], ["id"])
        batch.create_foreign_key("fk_ocr_attachment", "material_attachment", ["attachment_id"], ["id"])
        batch.create_index("ix_ocr_material_version", ["material_record_id", "material_version"])


def downgrade():
    with op.batch_alter_table("ocr_job") as batch:
        batch.drop_index("ix_ocr_material_version")
        batch.drop_constraint("fk_ocr_attachment", type_="foreignkey")
        batch.drop_constraint("fk_ocr_material", type_="foreignkey")
        for name in ("attachment_id", "material_version", "material_record_id"):
            batch.drop_column(name)
