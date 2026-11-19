from conftest import login
from extensions import db
from material_models import MaterialRecord
from workflow_models import ScoreEntry, StudentScoreSnapshot


def test_unmatched_material_appears_as_unreviewed_display_zero_without_score_fact(env, active_cycle):
    row = MaterialRecord(student_id="S1", faculty_id=1, category="competition",
                         year=2024, status="rule_unmatched", data={}, analysis={},
                         normalized_terms={"competition_name": "蓝桥杯",
                                           "award_level": "三等奖"})
    db.session.add(row); db.session.commit()
    login(env[1], env[2]["student"])
    response = env[1].get("/api/workflow/students/S1/score/current")
    assert response.status_code == 200
    data = response.json
    assert data["status"] == "no_authoritative_snapshot"
    assert data["snapshot_id"] is None and data["comprehensive_score"] is None
    assert len(data["entries"]) == 1
    item = data["entries"][0]
    assert item["included_score"] == "0" and item["verification_status"] == "unreviewed"
    assert item["scoring_status"] == "rule_unmatched"
    assert item["exclusion_reason"] == "材料词条没有对应计分"
    assert item["id"] is None and item["score_entry_id"] is None
    assert ScoreEntry.query.count() == 0 and StudentScoreSnapshot.query.count() == 0


def test_student_score_contract_does_not_expose_other_students_pending_material(env, active_cycle):
    row = MaterialRecord(student_id="S1", faculty_id=1, category="competition",
                         year=2026, status="rule_unmatched", data={}, analysis={},
                         normalized_terms={"competition_name": "蓝桥杯",
                                           "award_level": "三等奖"})
    db.session.add(row); db.session.commit()
    login(env[1], env[2]["student"])
    assert env[1].get("/api/workflow/students/OTHER/score/current").status_code == 404
    login(env[1], env[2]["other"])
    assert env[1].get("/api/workflow/students/S1/score/current").status_code == 403
