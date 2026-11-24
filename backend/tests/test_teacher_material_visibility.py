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


def test_history_keyword_matches_names_and_student_suffix_before_pagination(env):
    reviewer = teacher(env)
    for status, name, student_id, faculty_id in (
        ("verified", "其他项目", "sample2602", 1),
        ("verified", "交互设计 100%", "sample2602", 1),
        ("rejected", "交互设计 100%", "other2602", 1),
        ("submitted", "交互设计 100%", "sample2602", 1),
        ("verified", "交互设计 100%", "sample2602", 2),
    ):
        db.session.add(MaterialRecord(student_id=student_id, faculty_id=faculty_id,
            category="arts_sports", year=2028, status=status, data={"project_name": name}, analysis={}))
    db.session.commit()
    client = env[1]
    login(client, reviewer.id)
    url = "/api/materials/arts_sports/records"

    def search(term, **params):
        response = client.get(url, query_string={"reviewed": "1", "keyword": term, **params})
        assert response.status_code == 200
        return response.json

    first = search("交互设计", limit=1)
    assert [row["status"] for row in first["records"]] == ["verified"]
    second = search("交互设计", after_id=first["next_after_id"], limit=1)
    assert [row["status"] for row in second["records"]] == ["rejected"]
    assert second["next_after_id"] is None
    assert len(search("2602")["records"]) == 3
    assert len(search("SAMPLE2602")["records"]) == 2
    assert len(search("100%")["records"]) == 2
    assert search("%_")["records"] == []
