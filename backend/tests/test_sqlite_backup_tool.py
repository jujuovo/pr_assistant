"""SQLite 一致性备份工具：WAL 未落盘事务也要进备份，且不破坏源库。"""
import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.backup_sqlite import backup, restore  # noqa: E402


def _make_source(tmp_path, *, wal=True):
    source = tmp_path / "source.db"
    con = sqlite3.connect(source)
    if wal:
        con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE note (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
    con.executemany("INSERT INTO note (body) VALUES (?)", [("a",), ("b",)])
    con.commit()
    # 保持连接不关闭：模拟"服务正在运行、还有 -wal 未合并"
    return source, con


def test_backup_captures_wal_content_and_keeps_source_intact(tmp_path):
    source, live = _make_source(tmp_path)
    # 连接未关闭时再写一条，这条只会落在 -wal 里
    live.execute("INSERT INTO note (body) VALUES ('wal-only')")
    live.commit()
    assert (tmp_path / "source.db-wal").exists(), "WAL 文件应当存在"

    destination = tmp_path / "copy.db"
    result = backup(source, destination)

    assert result["integrity"] == "ok"
    assert result["journal_mode"] in {"wal", "memory"}

    copied = sqlite3.connect(destination)
    try:
        rows = [row[0] for row in copied.execute("select body from note order by id")]
    finally:
        copied.close()
    # 三行都要在：说明备份读到了 -wal 里尚未 checkpoint 的事务
    assert rows == ["a", "b", "wal-only"]

    # 源库仍然可用，数据没有被备份动作破坏
    assert live.execute("select count(*) from note").fetchone()[0] == 3
    live.close()


def test_backup_refuses_to_overwrite_without_force(tmp_path):
    source, live = _make_source(tmp_path)
    live.close()
    destination = tmp_path / "copy.db"
    backup(source, destination)
    with pytest.raises(FileExistsError):
        backup(source, destination)
    backup(source, destination, overwrite=True)


def test_backup_rejects_same_file(tmp_path):
    source, live = _make_source(tmp_path)
    live.close()
    with pytest.raises(ValueError):
        backup(source, source)


def test_restore_replaces_target_and_verifies(tmp_path):
    source, live = _make_source(tmp_path)
    live.close()
    snapshot = tmp_path / "snapshot.db"
    backup(source, snapshot)

    target = tmp_path / "target.db"
    con = sqlite3.connect(target)
    con.execute("CREATE TABLE note (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
    con.execute("INSERT INTO note (body) VALUES ('旧数据')")
    con.commit()
    con.close()

    result = restore(snapshot, target, overwrite=True)

    assert result["integrity"] == "ok"
    restored = sqlite3.connect(target)
    try:
        rows = [row[0] for row in restored.execute("select body from note order by id")]
    finally:
        restored.close()
    assert rows == ["a", "b"]


def test_backup_creates_missing_destination_directory(tmp_path):
    source, live = _make_source(tmp_path)
    live.close()
    destination = tmp_path / "nested" / "dir" / "copy.db"
    backup(source, destination)
    assert os.path.isfile(destination)
