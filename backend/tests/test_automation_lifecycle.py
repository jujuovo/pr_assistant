"""旧管理删除入口的保护回归。

批量志愿链路（`/api/automation/**`）已下线，不再有新的数据生产者，但历史环境里
`automation_*` 表可能仍有数据。`services/deletion.py` 的保护分支必须继续生效，
否则删除用户/学院/系/专业会连带丢掉旧志愿记录和原件。

原先这些用例是通过自动化接口造数据的；接口下线后改为直接用 ORM 构造。
"""
import io
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from conftest import login
from extensions import db
from legacy_models import Application
from models import Department, Faculty, Major, Student, SystemSettings, User
from automation_models import AutomationBatch, AutomationPolicy, AutomationReview

# 旧申请创建要求存在活动的推免周期政策。
pytestmark = pytest.mark.usefixtures("active_cycle_2025")


def _png_bytes():
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 200, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


def _seed_batch(student, *, status="approved"):
    batch = AutomationBatch(
        student_id=student.student_id, faculty_id=student.faculty_id, year=2025,
        material_type="credit", status=status, policy_snapshot={}, score_snapshot={},
        attempts=0, version=1,
    )
    db.session.add(batch)
    db.session.commit()
    return batch


@pytest.fixture
def deletion_env(env, tmp_path):
    from blueprints.admin_bp import admin_bp
    from blueprints.user_bp import user_bp

    app, client, users = env
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)
    app.config.update(
        FILE_FOLDER=str(tmp_path / "legacy_files"),
        UPLOAD_FOLDER=str(tmp_path / "legacy"),
    )
    db.session.add(SystemSettings(allowed_file_types=".png"))
    db.session.commit()
    db.session.execute(text("PRAGMA foreign_keys=ON"))
    assert db.session.execute(text("PRAGMA foreign_keys")).scalar() == 1

    student = Student.query.one()
    payload = {
        "studentId": student.student_id, "studentName": student.student_name,
        "facultyId": student.faculty_id, "departmentId": student.department_id,
        "majorId": student.major_id, "applicationType": "comprehensive",
        "projectName": "人工申请", "selfScore": 1,
    }
    login(client, users["student"])
    result = client.post(
        "/api/applications",
        data={"application": __import__("json").dumps(payload),
              "files": (io.BytesIO(_png_bytes()), "legacy.png")},
    )
    assert result.status_code == 201, result.data
    application = Application.query.one()
    attachment = Path(app.config["FILE_FOLDER"]) / Path(application.files[0]["path"]).name
    assert attachment.is_file()

    routes = {
        "user": f"/api/admin/users/{users['student']}",
        "faculty": f"/api/admin/faculties/{student.faculty_id}",
        "department": f"/api/admin/departments/{student.department_id}",
        "major": f"/api/admin/majors/{student.major_id}",
    }
    yield app, client, users, attachment, routes, application.id


def test_delete_user_with_legacy_batch_is_protected(deletion_env):
    """库里还有旧批量志愿记录时，删除该学生必须被阻止，原件也不能丢。"""
    app, client, users, attachment, routes, application_id = deletion_env
    student = Student.query.one()
    _seed_batch(student)

    login(client, users["admin"])
    response = client.delete(routes["user"])

    assert response.status_code == 409, response.data
    db.session.expire_all()
    assert db.session.get(User, users["student"]) is not None
    assert Student.query.filter_by(student_id="S1").count() == 1
    assert db.session.get(Application, application_id) is not None
    assert attachment.is_file()


def test_delete_reviewer_with_audit_is_protected(deletion_env):
    """审核人身上有旧批量志愿的审核记录时不能删除。"""
    app, client, users, attachment, routes, application_id = deletion_env
    batch = _seed_batch(Student.query.one())
    db.session.add(AutomationReview(batch_id=batch.id, reviewer_id=users["admin"], details={}))
    db.session.commit()

    db.session.get(User, users["other"]).role = "admin"
    db.session.commit()
    login(client, users["other"])
    response = client.delete(f"/api/admin/users/{users['admin']}")

    assert response.status_code == 409
    assert AutomationReview.query.count() == 1
    assert db.session.get(User, users["admin"]) is not None
    assert attachment.is_file()


def test_delete_faculty_with_only_policy_is_protected(deletion_env):
    app, client, users, attachment, routes, application_id = deletion_env
    student = Student.query.one()
    db.session.add(AutomationPolicy(faculty_id=student.faculty_id, year=2025,
                                    revision=1, config={}))
    db.session.commit()

    login(client, users["admin"])
    response = client.delete(routes["faculty"])

    assert response.status_code == 409
    assert "政策" in response.json["message"]
    assert attachment.is_file()


@pytest.mark.parametrize("route", ["user", "faculty", "department", "major"])
def test_normal_deletion_still_works_without_legacy_data(deletion_env, route):
    app, client, users, attachment, routes, application_id = deletion_env
    login(client, users["admin"])
    response = client.delete(routes[route])
    assert response.status_code == 200, response.data
    assert not attachment.exists()
    assert db.session.get(Application, application_id) is None
    assert db.session.get(User, users["student"]) is None
    assert Student.query.count() == 0


@pytest.mark.parametrize("route", ["user", "faculty", "department", "major"])
@pytest.mark.parametrize("integrity", [False, True])
def test_failed_commit_never_deletes_attachments(deletion_env, monkeypatch, route, integrity):
    app, client, users, attachment, routes, application_id = deletion_env
    login(client, users["admin"])

    def fail_commit():
        if integrity:
            raise IntegrityError("DELETE", {}, RuntimeError("foreign key violation"))
        raise RuntimeError("connection lost")

    monkeypatch.setattr(db.session, "commit", fail_commit)
    response = client.delete(routes[route])
    assert response.status_code == (409 if integrity else 500)
    assert attachment.is_file()
    assert db.session.get(Application, application_id) is not None
    assert db.session.get(User, users["student"]) is not None
    assert Student.query.count() == 1
