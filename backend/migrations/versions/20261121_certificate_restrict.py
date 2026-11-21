"""certificate assessment: 外键由 CASCADE 改为 RESTRICT

原来 `certificate_assessment.application_id` 是 `ondelete="CASCADE"`：
删除一条旧 `application` 会**静默**带走对应的证书评估记录，不报错、
也不留痕，事后无法恢复。证书评估是审核依据，必须显式处理。

改成 RESTRICT 后：存在评估记录时删除会被外键拦下，
调用方需要先显式清理或拒绝删除，从而把"丢数据"变成"看得见的冲突"。

Revision ID: 20261121_certificate_restrict
Revises: 20261120_volunteer_ocr
"""
from alembic import op
import sqlalchemy as sa

revision = "20261121_certificate_restrict"
down_revision = "20261120_volunteer_ocr"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("certificate_assessment", recreate="always") as batch:
        batch.drop_constraint("certificate_assessment_application_id_fkey", type_="foreignkey")
        batch.create_foreign_key(
            "certificate_assessment_application_id_fkey", "application",
            ["application_id"], ["id"], ondelete="RESTRICT",
        )


def downgrade():
    with op.batch_alter_table("certificate_assessment", recreate="always") as batch:
        batch.drop_constraint("certificate_assessment_application_id_fkey", type_="foreignkey")
        batch.create_foreign_key(
            "certificate_assessment_application_id_fkey", "application",
            ["application_id"], ["id"], ondelete="CASCADE",
        )
