from conftest import login
from extensions import db
from material_models import MaterialRecord
from models import User
from test_material_rule_submission import MATERIAL_TERMS, version


def make_row(status, rule_version_id=None):
    row = MaterialRecord(student_id="S1", faculty_id=1, category="competition",
                         year=2026, status=status, data={}, analysis={},
                         normalized_terms=MATERIAL_TERMS,
                         normalization_version="material-terms-v1",
                         rule_version_id=rule_version_id)
    db.session.add(row); db.session.commit()
    return row


def teacher(env):
    user = User(username="same-teacher", name="本院教师", password="test",
                role="teacher", status="active", faculty_id=1)
    db.session.add(user); db.session.commit()
    return user


def test_teacher_list_only_contains_formally_submitted_bound_material(env, active_cycle):
    reviewer = teacher(env)
    published = version(1)
    visible = make_row("submitted", published.id)
    make_row("rule_unmatched")
    make_row("rule_available")
    make_row("submitted")
    login(env[1], reviewer.id)
    response = env[1].get("/api/materials/competition/records")
    assert response.status_code == 200
    assert [item["id"] for item in response.json["records"]] == [visible.id]


def test_teacher_direct_links_and_forged_reviews_are_rejected(env, active_cycle):
    reviewer = teacher(env)
    for status in ("rule_unmatched", "rule_available"):
        row = make_row(status)
        login(env[1], reviewer.id)
        base = f"/api/materials/competition/records/{row.id}"
        assert env[1].get(base).status_code == 403
        reviewed = env[1].post(base + "/review", json={
            "version": row.version, "decision": "verified", "comment": "构造请求",
        })
        assert reviewed.status_code == 403


def test_submitted_without_fixed_rule_is_not_reviewable(env, active_cycle):
    reviewer = teacher(env); row = make_row("submitted")
    login(env[1], reviewer.id)
    base = f"/api/materials/competition/records/{row.id}"
    assert env[1].get(base).status_code == 403
    assert env[1].post(base + "/review", json={
        "version": 1, "decision": "verified", "comment": "无规则",
    }).status_code == 403
