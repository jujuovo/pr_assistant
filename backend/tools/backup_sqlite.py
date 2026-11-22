# -*- coding: utf-8 -*-
"""SQLite 一致性备份/恢复工具。

为什么需要它：
  - 仓库原有的 `db_backup.py` 全程依赖 `psycopg2.connect()` 与 `pg_dump`，
    对本地 SQLite 开发库完全不可用；
  - SQLite 处于 WAL 模式时，直接复制 `.db` 文件会**丢掉仍留在 `-wal` 里的最新事务**，
    复制出来的备份看起来正常，实际少数据。

本工具使用 SQLite 官方在线备份接口（`sqlite3.Connection.backup`），
它会在一个读事务里生成一致性快照，对 WAL 同样安全，且不需要停止服务。

用法：
  python -B backend/tools/backup_sqlite.py --source backend/instance/gradpush-dev.db
  python -B backend/tools/backup_sqlite.py --source <源库> --dest <目标文件> --force
  python -B backend/tools/backup_sqlite.py --restore --source <备份文件> --dest <目标库> --force
"""
import argparse
import os
import sqlite3
import sys

KEY_TABLES = ("student", "user", "material_record", "material_event", "score_entry")


def _connect_readonly(path):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"数据库不存在：{path}")
    return sqlite3.connect(path, timeout=30)


def _describe(path):
    con = _connect_readonly(path)
    try:
        journal = con.execute("PRAGMA journal_mode").fetchone()[0]
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {}
        for table in KEY_TABLES:
            try:
                counts[table] = con.execute(f'select count(*) from "{table}"').fetchone()[0]
            except sqlite3.Error:
                counts[table] = None
        return journal, integrity, counts
    finally:
        con.close()


def backup(source, destination, *, overwrite=False):
    """把 source 的一致性快照写到 destination；WAL 安全，可在线执行。"""
    source = os.path.abspath(source)
    destination = os.path.abspath(destination)
    if source == destination:
        raise ValueError("源与目标不能是同一个文件")
    if os.path.exists(destination) and not overwrite:
        raise FileExistsError(f"目标已存在，加 --force 覆盖：{destination}")

    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    src = sqlite3.connect(source, timeout=30)
    dst = sqlite3.connect(destination)
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()

    journal, integrity, counts = _describe(destination)
    if integrity != "ok":
        raise RuntimeError(f"备份完整性校验失败：{integrity}")
    return {"destination": destination, "journal_mode": journal,
            "integrity": integrity, "counts": counts}


def restore(backup_file, target, *, overwrite=False):
    """用备份文件覆盖目标库；恢复后校验完整性。"""
    backup_file = os.path.abspath(backup_file)
    target = os.path.abspath(target)
    if os.path.exists(target) and not overwrite:
        raise FileExistsError(f"目标库已存在，加 --force 覆盖：{target}")
    # 恢复同样走在线备份接口，避免留下 -wal 残留导致新旧数据混杂
    stale = []
    for suffix in ("-wal", "-shm"):
        try:
            os.remove(target + suffix)
        except FileNotFoundError:
            pass
        except OSError as exc:
            # Windows 上文件被其他连接占用时删不掉；此时强行恢复会让旧 WAL
            # 覆盖新数据，必须明确拒绝并告诉用户怎么处理。
            stale.append(f"{os.path.basename(target)}{suffix}（{exc.strerror or exc}）")
    if stale:
        raise RuntimeError(
            "目标库仍有连接未关闭，无法安全恢复：" + "、".join(stale)
            + "。请先停止后端服务与后台 worker，再重试恢复。"
        )
    src = sqlite3.connect(backup_file, timeout=30)
    dst = sqlite3.connect(target)
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()
    journal, integrity, counts = _describe(target)
    if integrity != "ok":
        raise RuntimeError(f"恢复后完整性校验失败：{integrity}")
    return {"target": target, "journal_mode": journal,
            "integrity": integrity, "counts": counts}


def main(argv=None):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_source = os.path.join(here, "instance", "gradpush-dev.db")
    parser = argparse.ArgumentParser(description="SQLite 一致性备份/恢复（WAL 安全）")
    parser.add_argument("--source", default=default_source, help="源库；--restore 时为备份文件")
    parser.add_argument("--dest", help="目标文件；默认与源库同目录、带时间戳")
    parser.add_argument("--restore", action="store_true", help="用 --source 指定的备份恢复 --dest 目标库")
    parser.add_argument("--force", action="store_true", help="允许覆盖已存在的目标")
    args = parser.parse_args(argv)

    if args.restore:
        if not args.dest:
            parser.error("--restore 需要同时指定 --dest 目标库")
        result = restore(args.source, args.dest, overwrite=args.force)
        print(f"恢复完成：{result['target']}")
    else:
        dest = args.dest
        if not dest:
            stamp = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
            dest = f"{os.path.splitext(os.path.abspath(args.source))[0]}.backup-{stamp}.db"
        result = backup(args.source, dest, overwrite=args.force)
        print(f"备份完成：{result['destination']}")
    print(f"  journal_mode={result['journal_mode']}  integrity={result['integrity']}")
    print("  关键表行数：" + "、".join(
        f"{name}={count}" for name, count in result["counts"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
