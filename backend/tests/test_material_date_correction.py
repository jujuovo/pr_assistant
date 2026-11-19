from conftest import login
from extensions import db
from material_models import MaterialEvent, MaterialRecord
from models import User
from test_material_rule_submission import TERMS, version
from use_cases.materials import create_correction_version


CONFIRMED = {"competition_name": "蓝桥杯", "award_level": "三等奖",
             "competition_level": "省级", "region": "福建赛区",
             "group": "软件类大学B组", "track": None,
             "award_date": "2026年5月8日"}


def old_record(env, active_cycle, published):
    row = MaterialRecord(
        student_id="S1", faculty_id=1, category="honor", year=2026,
        cycle_policy_version_id=active_cycle.id, status="verified_not_eligible",
        rule_version_id=published.id, version=4,
        data={"award_date": "2026-11-12"}, analysis={},
        confirmed_terms={**CONFIRMED, "award_date": "2026-11-12"},
        normalized_terms={**CONFIRMED, "award_date": "2026-11-12"},
        normalization_version="material-terms-v1", check_report={"reason": "outside"},
    )
    db.session.add(row); db.session.flush()
    db.session.add(MaterialEvent(record_id=row.id, actor_id=env[2]["admin"],
                                 action="reviewed", details={"old": True}))
    db.session.commit(); return row


def test_date_correction_creates_new_version_and_preserves_old_audit(env, active_cycle):
    student = db.session.get(User, env[2]["student"])
    published = version(1)
    old = old_record(env, active_cycle, published)
    corrected = create_correction_version(student, old, 4, CONFIRMED)
    db.session.commit()
    assert corrected.id != old.id and corrected.supersedes_record_id == old.id
    assert corrected.correction_sequence == 1 and corrected.status == "rule_available"
    assert corrected.data["award_date"] == "2026-05-08"
    assert corrected.cycle_policy_version_id == old.cycle_policy_version_id
    assert corrected.rule_version_id is None
    db.session.refresh(old)
    assert old.status == "verified_not_eligible" and old.data["award_date"] == "2026-11-12"
    assert MaterialEvent.query.filter_by(record_id=old.id, action="reviewed").count() == 1
    assert MaterialEvent.query.filter_by(
        record_id=corrected.id, action="correction_version_created"
    ).count() == 1


def test_date_correction_api_rejects_other_student_and_stale_version(env, active_cycle):
    published = version(1); old = old_record(env, active_cycle, published)
    login(env[1], env[2]["other"])
    path = f"/api/materials/honor/records/{old.id}/corrections"
    assert env[1].post(path, json={"version": 4, "confirmed_terms": CONFIRMED}).status_code == 403
    login(env[1], env[2]["student"])
    stale = env[1].post(path, json={"version": 3, "confirmed_terms": CONFIRMED})
    assert stale.status_code == 409 and stale.json["code"] == "version_conflict"
