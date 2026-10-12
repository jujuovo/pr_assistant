"""荣誉日期换序去重、旧指纹兼容与旧管理删除入口回归。"""
import hashlib
import io
import json
from pathlib import Path
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from conftest import login
from extensions import db
from models import Application, Student, User, Faculty, Department, Major, SystemSettings
from automation_models import AutomationBatch, AutomationItem, AutomationFingerprint, AutomationReview
from services.recognition.worker import run_one
from test_automation import policy, upload, view, submit, approve, honor, credit, Provider, image_bytes


def clear_activity_fingerprints(item):
    # 保留文件指纹，模拟升级前留在库里的旧版活动指纹。
    AutomationFingerprint.query.filter(AutomationFingerprint.item_id == item.id,
                                      AutomationFingerprint.kind != "file").delete(synchronize_session=False)
    db.session.add(AutomationFingerprint(student_id="S1", kind="honor_event",
        value=hashlib.sha256(b"legacy-date-order-key").hexdigest(), item_id=item.id))
    db.session.commit()


@pytest.mark.parametrize("different_recorded", [False, True])
@pytest.mark.parametrize("legacy", [False, True])
def test_honor_date_reordering_is_duplicate(env, different_recorded, legacy):
    app, client, users = env
    policy(client, users, max_score="10")
    first = upload(client, kind="honor")
    data = honor()
    data["rec_texts"][-1] = "2025.12.21、2025.12.22 活动A"
    run_one(app, Provider(data))
    submit(client, first)
    assert approve(client, users, first, "11.5").status_code == 200
    original = AutomationItem.query.filter_by(batch_id=first).one()
    if legacy:
        clear_activity_fingerprints(original)
    login(client, users["student"])
    second = upload(client, color="gray", kind="honor")
    data["rec_texts"][-1] = "2025年12月22日，2025/12/21 活动A"
    if different_recorded:
        data["rec_texts"][11] = "2026-09-1811:26:21"
    run_one(app, Provider(data))
    row = view(client, second)["rows"][0]
    assert row["status"] == "duplicate"
    assert row["duplicate_of"] == original.id
    assert not row["can_submit"]
    response = client.post(f"/api/automation/volunteer/batches/{second}/submit",
                           json={"version": view(client, second)["version"]})
    assert response.status_code == 400
    db.session.expire_all()
    assert Student.query.first().comprehensive_performance_total == pytest.approx(1.15)


@pytest.mark.parametrize("reason", ["2025.12.21、2025.12.23 活动A", "2025.12.22、2025.12.21 活动B"])
def test_honor_distinct_facts_not_false_duplicate(env, reason):
    app, client, users = env
    policy(client, users)
    first = upload(client, kind="honor")
    data = honor()
    data["rec_texts"][-1] = "2025.12.21、2025.12.22 活动A"
    run_one(app, Provider(data))
    second = upload(client, kind="honor", color="gray")
    data["rec_texts"][-1] = reason
    run_one(app, Provider(data))
    assert view(client, first)["rows"][0]["status"] == "ready"
    assert view(client, second)["rows"][0]["status"] == "ready"


def test_review_rechecks_normalized_historical_event_after_dates_added(env):
    app, client, users = env
    policy(client, users)
    first = upload(client, kind="honor")
    data = honor()
    data["rec_texts"][-1] = "2025.12.21、2025.12.22 活动A"
    run_one(app, Provider(data))
    submit(client, first)
    assert approve(client, users, first, "11.5").status_code == 200
    clear_activity_fingerprints(AutomationItem.query.filter_by(batch_id=first).one())
    login(client, users["student"])
    second = upload(client, kind="honor", color="gray")
    data["rec_texts"][11] = "2026-09-1811:26:21"
    data["rec_texts"][-1] = "活动A"
    run_one(app, Provider(data))
    submit(client, second)
    result = approve(client, users, second, "11.5", ["2025-12-22", "2025-12-21"])
    assert result.status_code == 409
    assert view(client, second)["status"] == "submitted"
    assert AutomationReview.query.count() == 1


@pytest.fixture
def deletion_env(env, tmp_path):
    from blueprints.user_bp import user_bp
    from blueprints.admin_bp import admin_bp
    app, client, users = env
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)
    app.config.update(FILE_FOLDER=str(tmp_path / "legacy_files"), UPLOAD_FOLDER=str(tmp_path / "legacy"))
    db.session.add(SystemSettings(allowed_file_types=".png"))
    db.session.commit()
    db.session.execute(text("PRAGMA foreign_keys=ON"))
    assert db.session.execute(text("PRAGMA foreign_keys")).scalar() == 1
    student = Student.query.one()
    payload = {"studentId": student.student_id, "studentName": student.student_name,
               "facultyId": student.faculty_id, "departmentId": student.department_id,
               "majorId": student.major_id, "applicationType": "comprehensive",
               "projectName": "人工申请", "selfScore": 1}
    result = client.post("/api/applications", data={"application": json.dumps(payload),
                         "files": (io.BytesIO(image_bytes()), "legacy.png")})
    assert result.status_code == 201, result.data
    application = Application.query.one()
    attachment = Path(app.config["FILE_FOLDER"]) / Path(application.files[0]["path"]).name
    assert attachment.is_file()
    routes = {"user": f"/api/admin/users/{users['student']}",
              "faculty": f"/api/admin/faculties/{student.faculty_id}",
              "department": f"/api/admin/departments/{student.department_id}",
              "major": f"/api/admin/majors/{student.major_id}"}
    yield app, client, users, attachment, routes, application.id


@pytest.mark.parametrize("route", ["user", "faculty", "department", "major"])
@pytest.mark.parametrize("approved", [False, True])
def test_delete_with_automation_preserves_database_and_files(deletion_env, route, approved):
    app, client, users, attachment, routes, application_id = deletion_env
    policy(client, users)
    batch = upload(client)
    if approved:
        run_one(app, Provider(credit()))
        submit(client, batch)
        assert approve(client, users, batch, "5.05").status_code == 200
    item = AutomationItem.query.filter_by(batch_id=batch).one()
    evidence = Path(app.config["AUTOMATION_UPLOAD_FOLDER"]) / item.stored_name
    response = client.delete(routes[route])
    assert response.status_code == 409, response.data
    db.session.expire_all()
    assert db.session.get(User, users["student"]) is not None
    assert Student.query.filter_by(student_id="S1").count() == 1
    assert db.session.get(Application, application_id) is not None
    assert db.session.get(AutomationBatch, batch) is not None
    assert attachment.is_file()
    assert evidence.is_file()


def test_delete_reviewer_with_audit_is_protected(deletion_env):
    app, client, users, attachment, routes, application_id = deletion_env
    policy(client, users)
    batch = upload(client)
    run_one(app, Provider(credit()))
    submit(client, batch)
    assert approve(client, users, batch, "5.05").status_code == 200
    response = client.delete(f"/api/admin/users/{users['admin']}")
    assert response.status_code == 409
    assert AutomationReview.query.count() == 1
    assert db.session.get(User, users["admin"]) is not None
    assert attachment.is_file()


def test_delete_faculty_with_only_policy_is_protected(deletion_env):
    app, client, users, attachment, routes, application_id = deletion_env
    policy(client, users)
    response = client.delete(routes["faculty"])
    assert response.status_code == 409
    assert "政策" in response.json["message"]
    assert attachment.is_file()


@pytest.mark.parametrize("route", ["user", "faculty", "department", "major"])
def test_normal_deletion_still_works_without_automation(deletion_env, route):
    app, client, users, attachment, routes, application_id = deletion_env
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
