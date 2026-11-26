"""Retire the unused certificate queue after its evidence has been archived."""
from importlib import import_module

from alembic import op
import sqlalchemy as sa


revision = "20261125_retire_cert_queue"
down_revision = "20261125_event_action_width"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if not sa.inspect(connection).has_table("certificate_assessment"):
        return
    if connection.dialect.name == "postgresql":
        connection.exec_driver_sql("LOCK TABLE certificate_assessment IN ACCESS EXCLUSIVE MODE")
    # SQLite must hold the write lock across the preflight and DROP, including
    # when the driver's legacy transaction mode does not start one for SELECT.
    elif connection.dialect.name == "sqlite":
        connection.exec_driver_sql("DELETE FROM certificate_assessment WHERE 1 = 0")
    if connection.execute(sa.text("SELECT id FROM certificate_assessment LIMIT 1")).first():
        raise RuntimeError("旧证书队列仍有证据记录，请先备份并迁移，再执行升级")
    op.drop_table("certificate_assessment")


def downgrade():
    if sa.inspect(op.get_bind()).has_table("certificate_assessment"):
        return
    original = import_module("migrations.versions.20261013_certificate_assessment")
    restricted = import_module("migrations.versions.20261121_certificate_restrict")
    original.upgrade()
    restricted.upgrade()
