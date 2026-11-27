"""Retire empty application tables and their two remaining optional links."""
from alembic import op
import sqlalchemy as sa

revision = "20261125_retire_application"
down_revision = "20261125_retire_cert_queue"
branch_labels = depends_on = None

ARCHIVE = ("certificate_assessment", "legacy_backfill_item", "legacy_backfill_batch", "application")
LINKED = ("material_record", "automation_batch")
SOURCES = ("application", "legacy_application", "certificate", "volunteer_automation")


def retire(connection, operations):
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    quote = connection.dialect.identifier_preparer.quote
    moving = set(ARCHIVE) & tables
    columns = {t: {c["name"] for c in inspector.get_columns(t)} for t in tables}
    linked = [t for t in LINKED if "application_id" in columns.get(t, ())]
    ledgers = [t for t in tables if "source_type" in columns[t]]
    if connection.dialect.name == "postgresql":
        locked = sorted(moving | set(linked) | set(ledgers))
        if locked:
            connection.exec_driver_sql("LOCK TABLE " + ", ".join(map(quote, locked)) + " IN ACCESS EXCLUSIVE MODE")
    for table in sorted(moving):
        if connection.exec_driver_sql(f"SELECT 1 FROM {quote(table)} LIMIT 1").first():
            raise ValueError(f"{table} 仍含历史记录，需要先归档或迁移")
    for table in ledgers:
        stmt = sa.text(f"SELECT 1 FROM {quote(table)} WHERE source_type IN :sources LIMIT 1")
        stmt = stmt.bindparams(sa.bindparam("sources", expanding=True))
        if connection.execute(stmt, {"sources": SOURCES}).first():
            raise ValueError(f"{table} 仍含旧来源计分记录")
    for table in linked:
        if connection.exec_driver_sql(f"SELECT 1 FROM {quote(table)} WHERE application_id IS NOT NULL LIMIT 1").first():
            raise ValueError(f"{table} 仍有关联旧申请的记录")
    for table in tables - moving:
        for fk in inspector.get_foreign_keys(table):
            if fk["referred_table"] in moving and not (
                table in linked and fk["constrained_columns"] == ["application_id"]
                and fk["referred_table"] == "application"
            ):
                raise ValueError(f"{table} 存在额外的旧表引用，需要人工迁移")
    for table in linked:
        if connection.dialect.name == "sqlite":
            trigger = connection.execute(sa.text(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=:table LIMIT 1"
            ), {"table": table}).first()
            if trigger:
                raise ValueError(f"{table} 存在自定义触发器，需要人工迁移")
        with operations.batch_alter_table(table) as batch:
            batch.drop_column("application_id")
    for table in ARCHIVE:
        if table in tables:
            operations.drop_table(table)


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        retire(connection, op)
        return
    # A parent-table rebuild with FK enforcement on can cascade into child rows.
    # Use a private migration connection, one explicit SQLite transaction and a
    # full FK check before commit. A retry after schema commit is idempotent.
    with op.get_context().autocommit_block():
        execute = connection.exec_driver_sql
        enabled = execute("PRAGMA foreign_keys").scalar_one()
        execute("PRAGMA foreign_keys=OFF")
        try:
            if execute("PRAGMA foreign_keys").scalar_one():
                raise RuntimeError("未获得独立迁移连接")
            execute("BEGIN IMMEDIATE")
            try:
                retire(connection, op)
                if execute("PRAGMA foreign_key_check").first():
                    raise ValueError("外键检查失败，已取消升级")
                execute("COMMIT")
            except BaseException:
                execute("ROLLBACK")
                raise
        finally:
            execute("PRAGMA foreign_keys=" + ("ON" if enabled else "OFF"))


def downgrade():
    raise RuntimeError("退役前的历史数据只能从备份恢复，请随旧版程序恢复升级前的数据库副本")
