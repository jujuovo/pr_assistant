from conftest import login
from extensions import db
from material_models import MaterialRecord
from models import User


TERMS = {"competition_name": "蓝桥杯", "award_level": "三等奖",
         "competition_level": "省级", "region": "福建赛区",
         "group": "软件类大学B组", "track": None}


def register(env):
    from blueprints.rule_bp import rule_bp
    env[0].register_blueprint(rule_bp)


def test_uncovered_terms_are_aggregated_and_privacy_safe(env):
    register(env)
    for index in range(2):
        db.session.add(MaterialRecord(
            student_id="S1", faculty_id=1, category="competition", year=2026,
            status="rule_unmatched", data={"private": index}, analysis={},
            normalized_terms=TERMS, normalization_version="material-terms-v1",
        ))
    db.session.commit()
    login(env[1], env[2]["admin"])
    response = env[1].get("/api/structured-rules/uncovered-terms")
    assert response.status_code == 200
    assert response.json == {"items": [{
        "cycle_code": 2026, "faculty_id": 1, "material_category": "competition",
        "normalized_terms": TERMS, "affected_count": 2,
    }]}
    serialized = str(response.json)
    assert "student_id" not in serialized and "attachments" not in serialized
    assert "private" not in serialized


def test_uncovered_terms_require_same_faculty_admin(env):
    register(env)
    other_admin = User(username="other-admin", name="外院管理员", password="test",
                       role="admin", status="active", faculty_id=2)
    db.session.add_all([other_admin, MaterialRecord(
        student_id="S1", faculty_id=1, category="competition", year=2026,
        status="rule_unmatched", data={}, analysis={}, normalized_terms=TERMS,
    )]); db.session.commit()
    login(env[1], other_admin.id)
    assert env[1].get("/api/structured-rules/uncovered-terms").json == {"items": []}
    login(env[1], env[2]["other"])
    assert env[1].get("/api/structured-rules/uncovered-terms").status_code == 403
