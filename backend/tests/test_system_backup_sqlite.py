"""管理员系统维护：备份/恢复在 SQLite 方言下也要真正可用，且只能管理员调用。

背景：`db_backup.py` 与 `system_bp.py` 原来全程依赖 `psycopg2` 和
`information_schema`，本地 SQLite 库上管理员点"立即备份"必然 500。

这里验证三件事：
1. SQLite 这条路径能出包、能列出、能下载、能恢复，且 WAL 里未合并的事务不会丢；
2. 恢复会把数据库回滚到备份时刻，并留下恢复前快照；
3. `/api/system/*` 不再是匿名可调用的破坏性接口。
"""
import io
import os
import sqlite3
import sys
import zipfile
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db_backup
from config import Config
from extensions import db
from models import User


def _uri(path):
    return f"sqlite:///{Path(path).as_posix()}"


@pytest.fixture
def sqlite_env(tmp_path, monkeypatch):
    """真实落盘的 SQLite 库 + 独立的备份目录与上传目录。"""
    db_path = tmp_path / "gradpush-t.db"
    backups = tmp_path / "backups"
    uploads = tmp_path / "uploads"
    backups.mkdir()
    uploads.mkdir()

    # db_backup 在调用时读取 Config，因此这里改的是类属性
    monkeypatch.setattr(Config, "SQLALCHEMY_DATABASE_URI", _uri(db_path), raising=False)
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(uploads), raising=False)

    app = Flask("system_backup_test")
    app.config.update(
        TESTING=True,
        SECRET_KEY="test",
        SQLALCHEMY_DATABASE_URI=_uri(db_path),
        UPLOAD_FOLDER=str(uploads),
    )
    db.init_app(app)

    from blueprints.system_bp import system_bp

    app.register_blueprint(system_bp)
    # 别把测试产生的备份写进仓库里的 backend/backup
    monkeypatch.setattr(
        "blueprints.system_bp.BACKUP_FOLDER", str(backups), raising=False
    )

    with app.app_context():
        db.create_all()
        admin = User(
            username="admin", name="管理员", password="test", role="admin", status="active"
        )
        student = User(
            username="stu", name="学生", password="test", role="student", status="active"
        )
        db.session.add_all([admin, student])
        db.session.commit()
        user_ids = {"admin": admin.id, "student": student.id}

    yield app, db_path, backups, uploads, user_ids

    with app.app_context():
        db.session.remove()


def _login(client, user_id):
    with client.session_transaction() as state:
        state["user_id"] = user_id


def _admin_client(app, user_ids):
    client = app.test_client()
    _login(client, user_ids["admin"])
    return client


def _write_note(db_path, body):
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS note (id INTEGER PRIMARY KEY, body TEXT NOT NULL)"
        )
        con.execute("INSERT INTO note (body) VALUES (?)", (body,))
        con.commit()
    finally:
        con.close()


def _read_notes(db_path):
    con = sqlite3.connect(db_path)
    try:
        return [row[0] for row in con.execute("SELECT body FROM note ORDER BY id")]
    finally:
        con.close()


# --------------------------------------------------------------------------
# 鉴权：这组端点以前完全开放
# --------------------------------------------------------------------------

def test_system_endpoints_reject_anonymous_callers(sqlite_env):
    app, db_path, backups, uploads, user_ids = sqlite_env
    client = app.test_client()

    for method, path in (
        ("post", "/api/system/backup"),
        ("post", "/api/system/restore"),
        ("post", "/api/system/restore/upload"),
        ("get", "/api/system/backups"),
        ("get", "/api/system/logs"),
        ("post", "/api/system/cache/clear"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 401, f"{path} 未登录时应拒绝"
        assert response.get_json()["success"] is False

    # 不能因为鉴权失败就顺手把备份造出来
    assert list(backups.iterdir()) == []


def test_system_endpoints_reject_non_admin(sqlite_env):
    app, db_path, backups, uploads, user_ids = sqlite_env
    client = app.test_client()
    _login(client, user_ids["student"])

    response = client.post("/api/system/backup")
    assert response.status_code == 403
    assert response.get_json()["success"] is False
    assert list(backups.iterdir()) == []


# --------------------------------------------------------------------------
# 方言识别
# --------------------------------------------------------------------------

def test_sqlite_database_path_recognises_only_local_file_databases():
    assert db_backup.is_sqlite_database("postgresql://localhost/gradpush") is False
    # 内存库没有可备份的文件，必须落回"不是 SQLite 文件库"
    assert db_backup.is_sqlite_database("sqlite://") is False
    assert db_backup.sqlite_database_path("sqlite:///:memory:") is None


def test_sqlite_database_path_strips_query_string(tmp_path):
    # 必须用当前平台的绝对路径：在 macOS/Linux 上 "C:/..." 不是绝对路径，
    # 会被当成相对路径拼到 instance/ 下，写死盘符的断言只能在 Windows 通过。
    absolute = tmp_path / "data" / "gradpush.db"
    parsed = db_backup.sqlite_database_path(
        f"sqlite:///{absolute.as_posix()}?check_same_thread=false"
    )
    assert parsed == os.path.normpath(str(absolute))


def test_sqlite_database_path_resolves_relative_into_instance_dir():
    relative = db_backup.sqlite_database_path("sqlite:///gradpush.db")
    assert relative == os.path.normpath(
        os.path.join(db_backup._BACKEND_ROOT, "instance", "gradpush.db")
    )


def test_uploads_backup_path_keeps_sqlite_extension_intact():
    # 回归：旧写法 str.replace(".sql", "_uploads.zip") 会把
    # "x_database.sqlite" 拼成 "x_database_uploads.zipite"
    assert db_backup.uploads_backup_path("x_database.sqlite") == "x_database_uploads.zip"
    assert db_backup.uploads_backup_path("x_database.sql") == "x_database_uploads.zip"
    assert db_backup.uploads_backup_path("a/b/x.sqlite") == "a/b/x_uploads.zip"


# --------------------------------------------------------------------------
# 备份
# --------------------------------------------------------------------------

def test_python_backup_captures_wal_resident_rows(sqlite_env, tmp_path):
    app, db_path, backups, uploads, user_ids = sqlite_env
    # 独立连接保持打开，模拟"服务在跑、事务还留在 -wal 里"
    live = sqlite3.connect(db_path)
    live.execute("PRAGMA journal_mode=WAL")
    live.execute("CREATE TABLE note (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
    live.execute("INSERT INTO note (body) VALUES ('wal-only')")
    live.commit()

    target = tmp_path / "snapshot.sqlite"
    with app.app_context():
        db_backup.backup_database_python(str(target))

    con = sqlite3.connect(target)
    try:
        assert con.execute("SELECT body FROM note").fetchall() == [("wal-only",)]
    finally:
        con.close()
        live.close()


def test_system_backup_endpoint_returns_restorable_zip(sqlite_env):
    app, db_path, backups, uploads, user_ids = sqlite_env
    client = _admin_client(app, user_ids)

    response = client.post("/api/system/backup")
    body = response.get_json()
    assert response.status_code == 200
    assert body["success"] is True

    name = body["backup_file"]
    assert name.startswith("gradpush_backup_") and name.endswith(".zip")

    with zipfile.ZipFile(backups / name) as archive:
        members = archive.namelist()
    assert any(member.endswith("_database.sqlite") for member in members)
    assert any(member.endswith("_uploads.zip") for member in members)

    # 列表接口要能列出它，否则管理员页面的"已有备份"永远是空的
    listed = client.get("/api/system/backups")
    payload = listed.get_json()
    assert payload["success"] is True
    assert [item["name"] for item in payload["backups"]] == [name]
    info = payload["backups"][0]
    assert info["download_url"] == f"/api/system/backup/download/{name}"
    assert info["size"] > 0
    assert info["create_time"]

    # 下载接口要能真的把包发出来
    download = client.get(info["download_url"])
    assert download.status_code == 200
    assert len(download.data) == info["size"]


def test_backup_bundle_includes_uploads_directory(sqlite_env):
    app, db_path, backups, uploads, user_ids = sqlite_env
    (uploads / "evidence").mkdir()
    (uploads / "evidence" / "proof.txt").write_text("hello", encoding="utf-8")

    client = _admin_client(app, user_ids)
    name = client.post("/api/system/backup").get_json()["backup_file"]

    with zipfile.ZipFile(backups / name) as archive:
        inner_name = next(
            member for member in archive.namelist() if member.endswith("_uploads.zip")
        )
        inner = zipfile.ZipFile(io.BytesIO(archive.read(inner_name)))
        assert any("proof.txt" in member for member in inner.namelist())


# --------------------------------------------------------------------------
# 恢复
# --------------------------------------------------------------------------

def test_system_restore_rolls_database_back_to_snapshot(sqlite_env):
    app, db_path, backups, uploads, user_ids = sqlite_env
    client = _admin_client(app, user_ids)

    _write_note(db_path, "before-backup")
    name = client.post("/api/system/backup").get_json()["backup_file"]
    _write_note(db_path, "after-backup")
    assert _read_notes(db_path) == ["before-backup", "after-backup"]

    response = client.post("/api/system/restore", json={"filename": name})
    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert _read_notes(db_path) == ["before-backup"]

    # 恢复前快照要留下来：误点恢复不该是不可逆操作
    assert list(db_path.parent.glob(f"{db_path.name}.before-restore-*"))


def test_system_restore_reports_missing_backup(sqlite_env):
    app, db_path, backups, uploads, user_ids = sqlite_env
    client = _admin_client(app, user_ids)

    response = client.post(
        "/api/system/restore", json={"filename": "gradpush_backup_19990101_000000.zip"}
    )
    assert response.status_code == 404
    assert response.get_json()["success"] is False


def test_restore_refuses_when_snapshot_has_no_database_file(sqlite_env):
    app, db_path, backups, uploads, user_ids = sqlite_env
    bogus = backups / "gradpush_backup_20200101_000000.zip"
    with zipfile.ZipFile(bogus, "w") as archive:
        archive.writestr("readme.txt", "not a database")

    with app.app_context():
        assert db_backup.restore_database_python(str(bogus)) is False
