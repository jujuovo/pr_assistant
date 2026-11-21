from decimal import Decimal

from conftest import login
from extensions import db
from models import Rule, Student
from use_cases.scoring import rebuild_student_snapshot
from workflow_models import RuleVersion, ScoreEntry


def _seed(env):
    student = Student.query.filter_by(student_id="S1").one()
    rule = Rule(name="竞赛", type="academic", sub_type="competition", score=5)
    db.session.add(rule)
    db.session.flush()
    data = {"score": 5, "max_count": 1}
    version = RuleVersion(
        rule_id=rule.id,
        version=1,
        status="published",
        snapshot=data,
        digest=RuleVersion.canonical_digest(data),
    )
    db.session.add(version)
    db.session.flush()
    for source_id, score in (("1", "5"), ("2", "3")):
        db.session.add(ScoreEntry(
            student_id="S1", faculty_id=student.faculty_id, year=2026,
            score_group="academic", category="competition", source_type="material",
            source_id=source_id, source_revision=1, rule_version_id=version.id,
            raw_score=Decimal(score), adjusted_score=Decimal(score),
            effective_score=Decimal(score), included=True, status="active",
            idempotency_key=f"explain:{source_id}",
        ))
    db.session.flush()
    rebuild_student_snapshot("S1", 2026)
    db.session.commit()


def test_student_score_contract_explains_totals_rules_and_exclusions(env):
    _seed(env)
    login(env[1], env[2]["student"])
    response = env[1].get("/api/workflow/students/S1/score?year=2026")
    assert response.status_code == 200
    data = response.json
    assert data["base"] == {"academic_score": "80.0000", "academic_weight": "80.0000"}
    assert data["categories"]["academic"] == {
        "raw_score": "5.0000", "effective_score": "5.0000",
        "note": "最终实际计分受本组上限影响。",
    }
    assert data["comprehensive_score"] == "69.0000"
    assert data["rule_version_ids"]
    assert data["rule_versions"][0]["label"] == "竞赛（第1版）"
    assert data["entries"][0]["rule_label"] == "竞赛（第1版）"
    assert data["updated_at"].endswith("Z")
    assert [entry["included"] for entry in data["entries"]] == [True, False]
    assert data["entries"][1]["exclusion_reason"] == "max_count_exceeded"
    assert set(data["entries"][0]) == {
        "id", "project_source", "verification_status", "scoring_status",
        "cycle_code", "cycle_policy_version_id", "rule_version_id",
        "automatic_score", "override_score", "candidate_score",
        "included_score", "item_bonus", "included", "exclusion_reason", "allowed_actions",
        "updated_at", "rule_label",
    }
    assert data["entries"][0]["project_source"] == {
        "type": "material", "id": "1", "category": "competition"
    }
    assert data["entries"][0]["automatic_score"] == "5.0000"
    assert data["entries"][0]["candidate_score"] == "5.0000"
    assert data["entries"][0]["included_score"] == "5.0000"


def test_score_contract_rejects_other_faculty(env):
    _seed(env)
    login(env[1], env[2]["other"])
    assert env[1].get("/api/workflow/students/S1/score?year=2026").status_code == 403


def test_current_score_resolves_active_cycle_and_preserves_historical_query(env, active_cycle):
    _seed(env)
    login(env[1], env[2]["student"])
    current = env[1].get("/api/workflow/students/S1/score/current")
    historical = env[1].get("/api/workflow/students/S1/score?year=2026")
    assert current.status_code == 200
    assert current.json["year"] == active_cycle.cycle_code == 2026
    assert historical.status_code == 200
    assert historical.json["snapshot_id"] == current.json["snapshot_id"]


def test_current_score_enforces_owner_and_staff_faculty_scope(env, active_cycle):
    _seed(env)
    login(env[1], env[2]["other"])
    assert env[1].get("/api/workflow/students/S1/score/current").status_code == 403
    login(env[1], env[2]["admin"])
    assert env[1].get("/api/workflow/students/S1/score/current").status_code == 200

