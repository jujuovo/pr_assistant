"""`/api/admin/*` 用户管理必须只认服务端会话。

原来的漏洞：这组端点没有任何鉴权，而且在函数体里用查询参数 `currentUserId`
判断"我是谁"。该参数由请求方随意填写，所以匿名请求就能：
  - 把任意账号（包括自己）的 role 改成 admin —— 直接提权；
  - 重置任意账号的密码 —— 直接接管；
  - 新建用户、删除用户、批量导入。

本文件锁住修复后的行为：匿名 401、非管理员 403、只有管理员能改别人，
且"不能操作自己"的判断也改成以会话为准。
"""
import sys
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extensions import db
from models import User


@pytest.fixture
def admin_env(tmp_path):
    app = Flask("admin_user_auth_test")
    app.config.update(
        TESTING=True,
        SECRET_KEY="test",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        UPLOAD_FOLDER=str(tmp_path / "uploads"),
        FILE_FOLDER=str(tmp_path / "uploads" / "files"),
    )
    db.init_app(app)

    from blueprints.user_bp import user_bp

    app.register_blueprint(user_bp)

    with app.app_context():
        db.create_all()
        admin = User(
            username="admin", name="管理员", password="test", role="admin", status="active"
        )
        victim = User(
            username="victim", name="目标学生", password="test", role="student", status="active"
        )
        other = User(
            username="other", name="别的老师", password="test", role="teacher", status="active"
        )
        db.session.add_all([admin, victim, other])
        db.session.commit()
        ids = {"admin": admin.id, "victim": victim.id, "other": other.id}

    yield app, ids

    with app.app_context():
        db.session.remove()


def _login(client, user_id):
    with client.session_transaction() as state:
        state["user_id"] = user_id


def _role_of(user_id):
    return db.session.get(User, user_id).role


# --------------------------------------------------------------------------
# 匿名：一条都不许通过
# --------------------------------------------------------------------------

def test_anonymous_cannot_promote_an_account_to_admin(admin_env):
    app, ids = admin_env
    response = app.test_client().put(
        f"/api/admin/users/{ids['victim']}", json={"role": "admin", "status": "active"}
    )
    assert response.status_code == 401
    with app.app_context():
        assert _role_of(ids["victim"]) == "student"


def test_anonymous_cannot_reset_any_password(admin_env):
    app, ids = admin_env
    response = app.test_client().post(
        f"/api/admin/users/{ids['victim']}/reset-password", json={"newPassword": "hacked"}
    )
    assert response.status_code == 401


def test_anonymous_cannot_create_or_delete_users(admin_env):
    app, ids = admin_env
    client = app.test_client()

    created = client.post(
        "/api/admin/create-users",
        json={"username": "ghost", "name": "幽灵", "role": "admin", "status": "active"},
    )
    assert created.status_code == 401

    deleted = client.delete(f"/api/admin/users/{ids['victim']}")
    assert deleted.status_code == 401

    with app.app_context():
        assert User.query.filter_by(username="ghost").first() is None
        assert db.session.get(User, ids["victim"]) is not None


def test_anonymous_cannot_list_users(admin_env):
    app, ids = admin_env
    assert app.test_client().get("/api/admin/users").status_code == 401


def test_anonymous_cannot_import_users(admin_env):
    app, ids = admin_env
    assert app.test_client().post("/api/admin/import-users").status_code == 401


# --------------------------------------------------------------------------
# 已登录的非管理员：403，且伪造 currentUserId 不再有用
# --------------------------------------------------------------------------

def test_non_admin_is_forbidden_even_with_spoofed_current_user_id(admin_env):
    app, ids = admin_env
    client = app.test_client()
    _login(client, ids["victim"])

    # 旧实现会拿这个参数当"我是谁"；现在必须被忽略
    response = client.put(
        f"/api/admin/users/{ids['other']}?currentUserId={ids['other']}",
        json={"role": "admin"},
    )
    assert response.status_code == 403
    with app.app_context():
        assert _role_of(ids["other"]) == "teacher"


# --------------------------------------------------------------------------
# 管理员：能改别人，不能改自己
# --------------------------------------------------------------------------

def test_admin_can_update_another_user(admin_env):
    app, ids = admin_env
    client = app.test_client()
    _login(client, ids["admin"])

    response = client.put(f"/api/admin/users/{ids['other']}", json={"name": "改过的名字"})
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(User, ids["other"]).name == "改过的名字"


def test_admin_cannot_update_delete_or_reset_self(admin_env):
    app, ids = admin_env
    client = app.test_client()
    _login(client, ids["admin"])

    assert client.put(f"/api/admin/users/{ids['admin']}", json={"name": "x"}).status_code == 400
    assert client.delete(f"/api/admin/users/{ids['admin']}").status_code == 400
    assert client.post(
        f"/api/admin/users/{ids['admin']}/reset-password", json={"newPassword": "x"}
    ).status_code == 400
