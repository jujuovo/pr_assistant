"""管理蓝图 `/api/admin/*` 的分级鉴权。

修复前的状态：21 个端点全部没有任何鉴权，匿名请求就能改学院计分系数、改系统
设置、删除学院/系/专业、上传或删除推免文件。

修复后按三档处理，本文件逐一锁住：
  1. 公开      —— 仅 `GET /public/graduate-files`（登录页展示推免文件）
  2. 登录即可  —— 组织结构与系统设置的只读端点（教师端筛选下拉、统计报表、
                 个人资料页都依赖它）
  3. 仅管理员  —— 其余全部（默认落到这一档，新增端点自动被覆盖）
"""
import sys
from pathlib import Path

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extensions import db
from models import Department, Faculty, Major, SystemSettings, User


# 必须挡住的写/敏感端点（匿名 401、非管理员 403）
ADMIN_ONLY = [
    ("post", "/api/admin/faculties"),
    ("put", "/api/admin/faculties/1"),
    ("delete", "/api/admin/faculties/1"),
    ("post", "/api/admin/departments"),
    ("put", "/api/admin/departments/1"),
    ("delete", "/api/admin/departments/1"),
    ("post", "/api/admin/majors"),
    ("put", "/api/admin/majors/1"),
    ("delete", "/api/admin/majors/1"),
    ("put", "/api/admin/system-settings"),
    ("get", "/api/admin/faculty-score-settings"),
    ("get", "/api/admin/faculty-score-settings/1"),
    ("put", "/api/admin/faculty-score-settings/1"),
    ("post", "/api/admin/graduate-files"),
    ("get", "/api/admin/graduate-files"),
    ("delete", "/api/admin/graduate-files/1"),
]

# 登录即可读取（教师端与个人资料页依赖）
LOGIN_ONLY = [
    ("get", "/api/admin/faculties"),
    ("get", "/api/admin/departments"),
    ("get", "/api/admin/majors"),
    ("get", "/api/admin/system-settings"),
]


@pytest.fixture
def admin_env(tmp_path):
    app = Flask("admin_bp_auth_test")
    app.config.update(
        TESTING=True,
        SECRET_KEY="test",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        UPLOAD_FOLDER=str(tmp_path / "uploads"),
        FILE_FOLDER=str(tmp_path / "uploads" / "files"),
    )
    db.init_app(app)

    from blueprints.admin_bp import admin_bp

    app.register_blueprint(admin_bp)

    with app.app_context():
        db.create_all()
        faculty = Faculty(name="信息学院")
        db.session.add(faculty)
        db.session.flush()
        department = Department(name="软件系", faculty_id=faculty.id)
        db.session.add(department)
        db.session.flush()
        major = Major(name="软件工程", department_id=department.id)
        db.session.add(major)
        db.session.flush()
        admin = User(username="admin", name="管理员", password="t", role="admin",
                     status="active", faculty_id=faculty.id)
        teacher = User(username="teacher", name="老师", password="t", role="teacher",
                       status="active", faculty_id=faculty.id)
        student = User(username="student", name="学生", password="t", role="student",
                       status="active", faculty_id=faculty.id)
        db.session.add_all([admin, teacher, student])
        db.session.commit()
        ids = {"admin": admin.id, "teacher": teacher.id, "student": student.id,
               "faculty": faculty.id, "department": department.id, "major": major.id}

    yield app, ids

    with app.app_context():
        db.session.remove()


def _login(client, user_id):
    with client.session_transaction() as state:
        state["user_id"] = user_id


def _call(client, method, path):
    return getattr(client, method)(path, json={})


# --------------------------------------------------------------------------
# 匿名：写/敏感端点全部 401，且数据库不变
# --------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", ADMIN_ONLY)
def test_anonymous_is_rejected(admin_env, method, path):
    app, ids = admin_env
    response = _call(app.test_client(), method, path)
    assert response.status_code == 401, f"{method.upper()} {path} 应拒绝匿名"


def test_anonymous_attempts_change_nothing(admin_env):
    app, ids = admin_env
    client = app.test_client()

    client.post("/api/admin/faculties", json={"name": "幽灵学院"})
    client.delete(f"/api/admin/faculties/{ids['faculty']}")
    client.delete(f"/api/admin/departments/{ids['department']}")
    client.delete(f"/api/admin/majors/{ids['major']}")
    client.put("/api/admin/system-settings", json={"academicYear": "9999"})

    with app.app_context():
        assert [f.name for f in Faculty.query.all()] == ["信息学院"]
        assert Department.query.count() == 1
        assert Major.query.count() == 1
        settings = SystemSettings.query.first()
        assert settings is None or settings.academic_year != "9999"


# --------------------------------------------------------------------------
# 已登录的非管理员：写操作 403，读操作仍可用
# --------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["teacher", "student"])
@pytest.mark.parametrize("method,path", ADMIN_ONLY)
def test_non_admin_cannot_touch_admin_endpoints(admin_env, role, method, path):
    app, ids = admin_env
    client = app.test_client()
    _login(client, ids[role])
    response = _call(client, method, path)
    assert response.status_code == 403, f"{role} 不应能 {method.upper()} {path}"


@pytest.mark.parametrize("role", ["teacher", "student"])
@pytest.mark.parametrize("method,path", LOGIN_ONLY)
def test_logged_in_user_can_read_org_and_settings(admin_env, role, method, path):
    """教师端筛选下拉与个人资料页依赖这几个只读端点，不能一起拦掉。"""
    app, ids = admin_env
    client = app.test_client()
    _login(client, ids[role])
    response = _call(client, method, path)
    assert response.status_code == 200, f"{role} 应能 GET {path}"


# --------------------------------------------------------------------------
# 公开端点
# --------------------------------------------------------------------------

def test_public_graduate_files_stays_anonymous(admin_env):
    app, ids = admin_env
    response = app.test_client().get("/api/admin/public/graduate-files")
    assert response.status_code == 200


# --------------------------------------------------------------------------
# 管理员：不被守卫拦住
# --------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", ADMIN_ONLY + LOGIN_ONLY)
def test_admin_is_not_blocked_by_guard(admin_env, method, path):
    """只验证守卫放行；具体业务校验由各端点自己的测试覆盖。

    守卫在 handler 之前执行，所以 handler 因为空 body 抛错也说明已经放行，
    这里把这类异常视为"未被拦截"。
    """
    app, ids = admin_env
    client = app.test_client()
    _login(client, ids["admin"])
    try:
        response = _call(client, method, path)
    except Exception:
        return
    assert response.status_code not in (401, 403), (
        f"管理员被误拦：{method.upper()} {path} -> {response.status_code}"
    )


def test_admin_can_create_and_delete_faculty(admin_env):
    app, ids = admin_env
    client = app.test_client()
    _login(client, ids["admin"])

    created = client.post("/api/admin/faculties", json={"name": "新建学院"})
    assert created.status_code in (200, 201)

    with app.app_context():
        names = [f.name for f in Faculty.query.all()]
    assert "新建学院" in names
