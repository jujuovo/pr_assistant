"""Protect old certificate evidence; support SQLite unnamed and PostgreSQL named FKs.

Revision ID: 20261121_certificate_restrict
Revises: 20261120_volunteer_ocr
"""
from alembic import op
import sqlalchemy as sa

revision = "20261121_certificate_restrict"
down_revision = "20261120_volunteer_ocr"
branch_labels = None
depends_on = None

TABLE = "certificate_assessment"
CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
GENERATED_NAME = "fk_certificate_assessment_application_id_application"


def _change_delete_rule(target):
    connection = op.get_bind()
    matches = [fk for fk in sa.inspect(connection).get_foreign_keys(TABLE)
               if fk["constrained_columns"] == ["application_id"]
               and fk["referred_table"] == "application"]
    if len(matches) != 1:
        raise RuntimeError("证书评估外键结构不符合预期，请先核对数据库；未开始重建表")
    fk = matches[0]
    if (fk.get("options", {}).get("ondelete") or "").upper() == target:
        return
    orphans = connection.execute(sa.text(
        "SELECT count(*) FROM certificate_assessment c LEFT JOIN application a "
        "ON a.id=c.application_id WHERE a.id IS NULL")).scalar_one()
    if orphans:
        raise RuntimeError(f"存在{orphans}条无对应申请的证书评估；请先人工对账，迁移未改写数据")
    sqlite = connection.dialect.name == "sqlite"
    name = fk["name"]
    if name is None and not sqlite:
        raise RuntimeError("无法确定原外键名称，请先核对数据库")
    # SQLite needs a reflected name for its unnamed historical constraint.
    # PostgreSQL can alter the constraint in place without recreating evidence rows.
    with op.batch_alter_table(TABLE, recreate="always" if sqlite else "auto",
                             naming_convention=CONVENTION if sqlite else None) as batch:
        batch.drop_constraint(name or GENERATED_NAME, type_="foreignkey")
        batch.create_foreign_key(name or GENERATED_NAME, "application",
                                 ["application_id"], ["id"], ondelete=target)


def upgrade():
    _change_delete_rule("RESTRICT")


def downgrade():
    _change_delete_rule("CASCADE")
