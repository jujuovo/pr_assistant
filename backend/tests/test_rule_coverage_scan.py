from conftest import login
from extensions import db
from material_models import MaterialEvent, MaterialRecord
from legacy_models import Application
from models import User
from workflow_models import ScoreEntry, StudentScoreSnapshot

from test_structured_rule_admin_api import payload


TERMS = {"competition_name": "蓝桥杯", "award_level": "三等奖",
         "competition_level": "省级", "region": "福建赛区",
         "group": "软件类大学B组", "track": None}


def register(env):
    from blueprints.rule_bp import rule_bp
    env[0].register_blueprint(rule_bp)


def test_publish_scan_only_marks_rule_available_and_is_idempotent(env, active_cycle):
    register(env); login(env[1], env[2]["admin"])
    row = MaterialRecord(student_id="S1", faculty_id=1, category="competition",
                         year=2024, status="rule_unmatched", data={}, analysis={},
                         normalized_terms=TERMS, normalization_version="material-terms-v1")
    db.session.add(row); db.session.commit()
    draft = env[1].post("/api/structured-rules/drafts", json=payload()).json
    published = env[1].post(
        f"/api/structured-rules/{draft['id']}/publish", json={"version": 1}
    )
    assert published.status_code == 200, published.json
    assert published.json["coverage_scan"]["available_count"] == 1
    db.session.refresh(row)
    assert row.status == "rule_available" and row.rule_version_id is None
    assert row.cycle_policy_version_id is None and row.year == 2024
    assert MaterialEvent.query.filter_by(record_id=row.id, action="mark_rule_available").count() == 1
    assert ScoreEntry.query.count() == 0 and StudentScoreSnapshot.query.count() == 0
    assert Application.query.filter_by(student_id="S1", status="pending").count() == 0

    admin = db.session.get(User, env[2]["admin"])
    from use_cases.structured_rules import scan_rule_coverage
    assert scan_rule_coverage(admin, cycle_code=2026)["available_count"] == 0
    db.session.commit()
    assert MaterialEvent.query.filter_by(record_id=row.id, action="mark_rule_available").count() == 1
