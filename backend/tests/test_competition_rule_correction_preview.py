import copy
import json
from pathlib import Path

from extensions import db
from models import User
from use_cases.competition_review import review_competition_material
from use_cases.competition_rules import (
    load_current_competition_package, preview_competition_package_correction,
)
from use_cases.materials import create_material


def _baseline(env):
    admin = db.session.get(User, env[2]["admin"])
    snapshot = json.loads((Path(__file__).parents[1] / "rules" / "competition_2028.json").read_text(encoding="utf-8"))
    package, _ = load_current_competition_package(admin, snapshot)
    student = db.session.get(User, env[2]["student"])
    row = create_material(student, "competition", {"year": 2028, "data": {
        "competition_id": "c09-computer-design", "project_name": "预览作品",
        "award_date": "2027-05-01", "level": "national",
        "award": "first_or_above", "event_year": 2027,
        "participation_mode": "individual",
    }})
    row.status = "submitted"
    teacher = User(username="preview-teacher", name="教师", password="test", role="teacher",
                   status="active", faculty_id=row.faculty_id)
    db.session.add(teacher); db.session.flush()
    return admin, snapshot, package, row, teacher


def test_identical_package_preview_has_no_impact_and_writes_nothing(env):
    admin, snapshot, package, row, _ = _baseline(env)
    db.session.flush()
    before = (package.status, row.status, row.version)
    report = preview_competition_package_correction(admin, copy.deepcopy(snapshot))
    assert report["affected_count"] == 0
    assert report["changed"] is False
    assert (package.status, row.status, row.version) == before
    assert not db.session.dirty


def test_score_change_preview_reports_old_new_and_historical_snapshot(env):
    admin, snapshot, package, row, teacher = _baseline(env)
    review_competition_material(teacher, row, {"version": row.version, "decision": "approve",
        "comment": "一致", "idempotency_key": "preview-approved"})
    db.session.flush()
    changed = copy.deepcopy(snapshot)
    changed["package_id"] = "xmu-competition-2028-correction"
    changed["score_matrix"]["national"]["first_or_above"]["A-"] = 12
    report = preview_competition_package_correction(admin, changed)
    impact = report["impacts"][0]
    assert report["affected_count"] == 1
    assert impact["old_match"]["candidate_score"] != impact["new_match"]["candidate_score"]
    assert impact["historical_score"]["score_entry_id"]
    assert package.status == "current" and row.status == "scored"


def test_mapping_change_preview_reports_unmatched_without_mutation(env):
    admin, snapshot, package, row, _ = _baseline(env)
    changed = copy.deepcopy(snapshot)
    changed["package_id"] = "xmu-competition-2028-catalog-correction"
    item = next(item for item in changed["catalog"] if item["competition_id"] == "c09-computer-design")
    item["levels"] = ["provincial"]
    report = preview_competition_package_correction(admin, changed)
    assert report["impacts"][0]["new_match"]["status"] == "unmatched"
    assert report["impacts"][0]["reasons"] == ["mapping_changed"]
    assert package.status == "current" and row.status == "submitted"
