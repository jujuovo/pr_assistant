from datetime import date
from decimal import Decimal

import pytest

from extensions import db
from models import Application, Rule, Student
from use_cases.scoring import ScoringUseCaseError, adapt_legacy_application
from workflow_models import RuleVersion, ScoreEntry, StudentScoreSnapshot


def _rule_with_version(sub_type="research"):
    rule = Rule(
        name="历史竞赛规则",
        type="academic",
        sub_type=sub_type,
        score=5,
        status="active",
    )
    db.session.add(rule)
    db.session.flush()
    snapshot = {"score": 5, "max_count": None}
    version = RuleVersion(
        rule_id=rule.id,
        version=1,
        status="published",
        snapshot=snapshot,
        digest=RuleVersion.canonical_digest(snapshot),
    )
    db.session.add(version)
    db.session.flush()
    return rule, version


def _application(student, rule, **overrides):
    values = {
        "student_id": student.student_id,
        "student_name": student.student_name,
        "faculty_id": student.faculty_id,
        "department_id": student.department_id,
        "major_id": student.major_id,
        "application_type": "academic",
        "project_name": "历史非竞赛材料",
        "award_date": date(2026, 5, 1),
        "cycle_code": 2026,
        "status": "approved",
        "final_score": 3.5,
        "rule_id": rule.id if rule else None,
    }
    values.update(overrides)
    row = Application(**values)
    db.session.add(row)
    db.session.flush()
    return row


def test_approved_application_maps_without_material_and_rebuilds_snapshot(env):
    student = Student.query.filter_by(student_id="S1").one()
    rule, version = _rule_with_version()
    application = _application(student, rule)

    result = adapt_legacy_application(application)
    db.session.commit()

    entry = db.session.get(ScoreEntry, result["score_entry_id"])
    assert result["status"] == "scored" and not result["replayed"]
    assert entry.source_type == "legacy_application"
    assert entry.source_id == str(application.id) and entry.source_revision == 1
    assert entry.material_record_id is None
    assert entry.rule_version_id == version.id
    assert entry.category == "research"
    assert entry.effective_score == Decimal("3.5000")
    snapshot = db.session.get(StudentScoreSnapshot, result["snapshot_id"])
    assert snapshot.year == 2026 and snapshot.specialty_score == Decimal("3.5000")


def test_legacy_adapter_never_infers_cycle_from_award_date(env):
    student = Student.query.filter_by(student_id="S1").one()
    rule, _version = _rule_with_version()
    application = _application(student, rule, cycle_code=None, award_date=date(2024, 5, 1))
    with pytest.raises(ScoringUseCaseError, match="fixed recommendation cycle"):
        adapt_legacy_application(application)


def test_repeated_adaptation_returns_existing_entry(env):
    student = Student.query.filter_by(student_id="S1").one()
    rule, _version = _rule_with_version()
    application = _application(student, rule)

    first = adapt_legacy_application(application)
    db.session.commit()
    second = adapt_legacy_application(application)
    db.session.commit()

    assert second["status"] == "scored" and second["replayed"]
    assert second["score_entry_id"] == first["score_entry_id"]
    assert ScoreEntry.query.filter_by(source_type="legacy_application").count() == 1
    assert StudentScoreSnapshot.query.count() == 1


def test_missing_published_rule_is_reported_without_zero_score(env):
    student = Student.query.filter_by(student_id="S1").one()
    rule = Rule(name="未版本化规则", type="academic", score=5, status="active")
    db.session.add(rule)
    db.session.flush()
    application = _application(student, rule)

    result = adapt_legacy_application(application)

    assert result == {
        "status": "needs_rule",
        "reason": "no_published_rule_version",
        "application_id": application.id,
    }
    assert ScoreEntry.query.count() == 0


def test_rejected_application_is_skipped(env):
    student = Student.query.filter_by(student_id="S1").one()
    rule, _version = _rule_with_version()
    application = _application(student, rule, status="rejected", final_score=0)

    result = adapt_legacy_application(application)

    assert result["status"] == "skipped"
    assert result["reason"] == "application_not_approved"
    assert ScoreEntry.query.count() == 0


def test_legacy_competition_application_is_never_projected_as_second_score_source(env):
    student = Student.query.filter_by(student_id="S1").one()
    rule, _version = _rule_with_version("competition")
    application = _application(student, rule)
    result = adapt_legacy_application(application)
    assert result == {"status": "skipped", "reason": "competition_requires_material_record",
                      "application_id": application.id}
    assert ScoreEntry.query.count() == 0
