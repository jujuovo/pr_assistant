"""文体活动手工材料：草稿、提交、我的材料、教师核验/退回与范围保护。"""
import io
import json

from conftest import login
from extensions import db
from material_models import MaterialAttachment, MaterialRecord
from models import Student, User
from workflow_models import ScoreEntry


DATA = {
    "document_type": "arts_competition",
    "project_name": "校运会田径比赛",
    "award_date": "2026-05-01",
}
PATH = "/api/materials/arts_sports/records"


def create(env, data=None, files=True):
    login(env[1], env[2]["student"])
    form = {"year": "2028", "data": json.dumps(data or DATA)}
    if files:
        form["files"] = (io.BytesIO(b"proof"), "proof.png")
    return env[1].post(PATH, data=form)


def submit(env, row):
    return env[1].post(f"{PATH}/{row['id']}/submit", json={"version": row["version"]})


def review(env, row, decision, comment=""):
    login(env[1], env[2]["admin"])
    return env[1].post(
        f"{PATH}/{row['id']}/review",
        json={"version": row["version"], "decision": decision, "comment": comment},
    )


def test_five_submission_types_save_as_manual_drafts(env):
    for kind in (
        "arts_competition",
        "performance",
        "arts_honor",
        "dorm_honor",
        "fitness_test",
    ):
        response = create(env, DATA | {"document_type": kind, "project_name": f"项目{kind}"})
        assert response.status_code == 201, response.json
        row = response.json
        assert row["status"] == "draft"
        assert row["manual_only"] is True
        assert row["data"]["document_type"] == kind
        assert row["allowed_actions"] and "submit" in row["allowed_actions"]
    assert MaterialRecord.query.count() == 5
    assert MaterialAttachment.query.count() == 5


def test_invalid_submission_fields_are_rejected_without_writes(env):
    for data in (
        DATA | {"document_type": "invalid"},
        DATA | {"project_name": "A"},
        DATA | {"project_name": "A" * 31},
        {"document_type": "arts_competition", "project_name": "校运会"},
    ):
        response = create(env, data)
        assert response.status_code == 400, response.json
    assert MaterialRecord.query.count() == MaterialAttachment.query.count() == 0


def test_draft_submit_and_my_materials_visibility(env):
    row = create(env).json
    login(env[1], env[2]["student"])
    listed = env[1].get(PATH)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json["records"]] == [row["id"]]
    submitted = submit(env, row)
    assert submitted.status_code == 200, submitted.json
    assert submitted.json["status"] == "submitted"
    assert ScoreEntry.query.count() == 0


def test_missing_attachment_is_rejected_at_submit(env):
    login(env[1], env[2]["student"])
    row = env[1].post(PATH, json={"year": 2028, "data": DATA})
    assert row.status_code == 201, row.json
    response = submit(env, row.json)
    assert response.status_code == 400
    assert response.json["error"]
    assert db.session.get(MaterialRecord, row.json["id"]).status == "draft"


def test_teacher_scope_and_return_then_student_resubmit(env):
    row = create(env).json
    row = submit(env, row).json
    login(env[1], env[2]["admin"])
    listed = env[1].get(PATH + "?reviewed=0")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json["records"]] == [row["id"]]

    returned = review(env, row, "needs_correction", "请补充比赛秩序册")
    assert returned.status_code == 200, returned.json
    assert returned.json["status"] == "needs_correction"

    login(env[1], env[2]["student"])
    edited = env[1].patch(
        f"{PATH}/{row['id']}",
        json={
            "version": returned.json["version"],
            "data": DATA | {"project_name": "校运会田径比赛（补正）"},
        },
    )
    assert edited.status_code == 200, edited.json
    assert edited.json["status"] == "draft"
    resubmitted = submit(env, edited.json)
    assert resubmitted.status_code == 200, resubmitted.json

    verified = review(env, resubmitted.json, "verified")
    assert verified.status_code == 200, verified.json
    assert verified.json["status"] == "verified"
    assert ScoreEntry.query.count() == 0


def test_return_requires_comment_and_other_faculty_is_rejected(env):
    row = submit(env, create(env).json).json
    login(env[1], env[2]["admin"])
    missing = env[1].post(
        f"{PATH}/{row['id']}/review",
        json={"version": row["version"], "decision": "needs_correction", "comment": ""},
    )
    assert missing.status_code == 400

    login(env[1], env[2]["other"])
    forbidden = env[1].get(f"{PATH}/{row['id']}")
    assert forbidden.status_code in (403, 404)


def test_other_student_cannot_read_or_submit(env):
    row = create(env).json
    login(env[1], env[2]["student"])
    student = Student.query.filter_by(student_id="S1").one()
    other_user = User(
        username="student2",
        name="李四",
        role="student",
        status="active",
        student_id="S2",
        faculty_id=student.faculty_id,
        department_id=student.department_id,
        major_id=student.major_id,
    )
    other_user.set_password("test")
    db.session.add(other_user)
    db.session.add(
        Student(
            student_id="S2",
            student_name="李四",
            faculty_id=student.faculty_id,
            department_id=student.department_id,
            major_id=student.major_id,
        )
    )
    db.session.commit()
    login(env[1], other_user.id)
    assert env[1].get(f"{PATH}/{row['id']}").status_code in (403, 404)
    assert submit(env, row).status_code in (403, 404)


def test_stale_version_is_rejected(env):
    row = create(env).json
    login(env[1], env[2]["student"])
    response = env[1].patch(
        f"{PATH}/{row['id']}",
        json={"version": row["version"] + 1, "data": DATA},
    )
    assert response.status_code == 409
    assert db.session.get(MaterialRecord, row["id"]).version == row["version"]


def test_student_summary_counts_all_current_materials_but_not_legacy_links(env):
    row = create(env).json
    row = submit(env, row).json
    review(env, row, "verified")
    login(env[1], env[2]["student"])
    summary = env[1].get("/api/materials/student/summary")
    assert summary.status_code == 200
    assert summary.json["approved_count"] == 1
    assert summary.json["submitted_count"] == 1
    assert summary.json["status_counts"] == {"verified": 1}

    db.session.add(
        MaterialRecord(
            student_id="S1",
            faculty_id=1,
            category="competition",
            year=2028,
            status="verified",
            data={},
            analysis={},
        )
    )
    db.session.add(
        MaterialRecord(
            student_id="S1",
            faculty_id=1,
            category="social_practice",
            year=2028,
            status="verified",
            data={},
            analysis={},
            application_id=999,
        )
    )
    db.session.commit()
    summary = env[1].get("/api/materials/student/summary")
    assert summary.json["approved_count"] == 2
    assert summary.json["submitted_count"] == 2


def test_student_summary_is_student_only(env):
    login(env[1], env[2]["admin"])
    assert env[1].get("/api/materials/student/summary").status_code == 403


def test_teacher_summary_counts_same_faculty_new_material_only(env):
    row = submit(env, create(env).json).json
    login(env[1], env[2]["admin"])
    summary = env[1].get("/api/materials/teacher/summary")
    assert summary.status_code == 200
    assert summary.json["pending_count"] == 1
    assert summary.json["status_counts"] == {"submitted": 1}

    db.session.add(
        MaterialRecord(
            student_id="S1",
            faculty_id=1,
            category="competition",
            year=2028,
            status="submitted",
            data={},
            analysis={},
        )
    )
    db.session.add(
        MaterialRecord(
            student_id="S1",
            faculty_id=1,
            category="social_practice",
            year=2028,
            status="submitted",
            data={},
            analysis={},
            application_id=999,
        )
    )
    db.session.commit()
    summary = env[1].get("/api/materials/teacher/summary")
    assert summary.json["pending_count"] == 1

    login(env[1], env[2]["other"])
    other = env[1].get("/api/materials/teacher/summary")
    assert other.status_code == 200
    assert other.json["pending_count"] == 0

    login(env[1], env[2]["student"])
    assert env[1].get("/api/materials/teacher/summary").status_code == 403
