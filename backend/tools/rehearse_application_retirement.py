"""Verify the Application cutover on an in-memory SQLite backup, without touching the source."""
import argparse
import sys
from importlib import import_module
import hashlib
import json
from pathlib import Path
import sqlite3

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
migration = import_module("migrations.versions.20261125_retire_application")
ARCHIVE, LINKED = migration.ARCHIVE, migration.LINKED


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def snapshot(conn):
    """Compare retained rows by value, including evidence, scores, JSON and ledger identifiers."""
    inspector = sa.inspect(conn)
    result = {}
    for table in sorted(set(inspector.get_table_names()) - set(ARCHIVE)):
        cols = [c["name"] for c in inspector.get_columns(table)
                if not (table in LINKED and c["name"] == "application_id")]
        projection = ", ".join(map(quote, cols))
        raw = conn.exec_driver_sql(f"SELECT {projection} FROM {quote(table)}")
        rows = sorted(hashlib.sha256(repr(tuple(row)).encode()).digest() for row in raw)
        indexes = sorted((idx["name"], idx["unique"], tuple(idx["column_names"]))
                         for idx in inspector.get_indexes(table))
        fks = sorted((tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]),
                      tuple(sorted(fk["options"].items()))) for fk in inspector.get_foreign_keys(table)
                     if fk["referred_table"] != "application")
        result[table] = (cols, len(rows), hashlib.sha256(b"".join(rows)).hexdigest(), indexes, fks)
    return result


def rehearse(source, output=None):
    if not source.is_file():
        raise ValueError("找不到指定的源库")
    memory = sqlite3.connect(":memory:")
    try:
        original = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            original.backup(memory)
        finally:
            original.close()
        engine = sa.create_engine("sqlite://", creator=lambda: memory)
        with engine.connect() as conn:
            execute = conn.exec_driver_sql
            execute("PRAGMA foreign_keys=ON")
            tables = set(sa.inspect(conn).get_table_names())
            if output and "alembic_version" in tables:
                raise ValueError("带版本号的数据库副本请使用 Alembic 升级")
            pre = snapshot(conn)
            conn.commit()
            ctx = MigrationContext.configure(conn, opts={"transactional_ddl": True})
            with Operations.context(ctx), ctx.begin_transaction():
                migration.upgrade()
            if set(ARCHIVE).intersection(sa.inspect(conn).get_table_names()):
                raise RuntimeError("副本仍有旧表")
            if pre != snapshot(conn):
                raise RuntimeError("保留表的数据、索引或外键发生变化")
            if execute("PRAGMA foreign_key_check").first() or execute("PRAGMA integrity_check").scalar() != "ok":
                raise RuntimeError("副本完整性核验失败")
            for table in sa.inspect(conn).get_table_names():
                if any(fk["referred_table"] in ARCHIVE for fk in sa.inspect(conn).get_foreign_keys(table)):
                    raise RuntimeError(f"{table} 仍引用历史表")
            conn.commit()
            if execute("PRAGMA foreign_keys").scalar() != 1:
                raise RuntimeError("外键约束未恢复")
            if output:
                with output.open("xb"):
                    pass
                try:
                    target = sqlite3.connect(output)
                    try:
                        memory.backup(target)
                    finally:
                        target.close()
                except BaseException:
                    output.unlink(missing_ok=True)
                    raise
            return {"retained_tables":len(pre), "materials":pre.get("material_record", [None,0])[1],
                    "attachments":pre.get("material_attachment", [None,0])[1],
                    "scores":pre.get("score_entry", [None,0])[1], "removed_tables":sorted(tables & set(ARCHIVE))}
    finally:
        memory.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, help="可选，保存到尚不存在的 SQLite 副本")
    args = parser.parse_args()
    try:
        print(json.dumps(rehearse(args.source, args.output), ensure_ascii=False))
    except ValueError as error:
        parser.exit(1, str(error) + "\n")
