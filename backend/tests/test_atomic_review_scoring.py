from datetime import date, datetime

import pytest

from extensions import db
from material_models import MaterialEvent, MaterialRecord
from legacy_models import Application
from models import Rule, Student, User
from use_cases.materials import create_material, review_material, submit_material
from workflow_models import (
    MaterialReviewCommand,
    RankingBatch,
    ScoreOverrideAudit,
    ScoreEntry,
    StudentScoreSnapshot,
)


COMPETITION = {
    "competition_name": "程序设计竞赛",
    "organizer": "主办单位",
    "competition_level": "省级",
    "award_level": "一等奖",
    "award_date": "2026-05-08",
}
MATCH_TERMS = {
    "competition_name": "程序设计竞赛", "award_level": "一等奖",
    "competition_level": "省级", "region": {"any": True},
    "group": {"any": True}, "track": {"any": True},
}


def _setup(env):
    student_user = db.session.get(User, env[2]["student"])
    admin = db.session.get(User, env[2]["admin"])
    student = Student.query.filter_by(student_id="S1").one()
    from use_cases.cycles import activate_cycle_policy, create_cycle_policy
    from use_cases.rule_versions import publish_rule_version
    policy, _ = create_cycle_policy(
        admin, 2026, date(2023, 9, 1), date(2026, 8, 31), "2026 推免周期"
    )
    activate_cycle_policy(admin, policy)
    rule = Rule(
        name="竞赛一等奖",
        type="academic",
        sub_type="honor",
        score=5,
        max_score=5,
        status="active",
        faculty_id=student.faculty_id,
        match_terms=MATCH_TERMS, match_schema_version="material-terms-v1",
    )
    db.session.add(rule)
    version, _ = publish_rule_version(rule, published_by=admin, cycle_code=2026)
    batch = RankingBatch(
        year=2026,
        faculty_id=student.faculty_id,
        major_id=student.major_id,
        scope_type="major",
        scope_definition={"major_id": student.major_id},
        cutoff_at=datetime(2026, 12, 31),
        rule_version_ids=[version.id],
        score_precision=4,
        status="draft",
        version=1,
        input_digest="a" * 64,
        created_by=admin.id,
    )
    db.session.add(batch)
    application = Application(
        student_id="S1", student_name=student.student_name,
        faculty_id=student.faculty_id, department_id=student.department_id,
        major_id=student.major_id, application_type="academic",
        project_name="程序设计竞赛", status="draft",
    )
    db.session.add(application); db.session.flush()
    row = MaterialRecord(student_id=student_user.student_id, faculty_id=student_user.faculty_id,
        category="honor", year=2026, status="draft", data=COMPETITION, analysis={},
        application_id=application.id, normalized_terms={
        "competition_name": "程序设计竞赛", "award_level": "一等奖",
        "competition_level": "省级", "region": None, "group": None, "track": None,
    }, normalization_version="material-terms-v1")
    db.session.add(row); db.session.flush()
    submit_material(student_user, row, 1)
    db.session.commit()
    return row, admin, batch, application, student


def test_review_score_snapshot_staleness_and_audit_commit_together(env):
    row, admin, batch, application, student = _setup(env)
    review_material(admin, row, 2, "verified", "核验通过", "atomic-review")
    db.session.commit()
    entry = ScoreEntry.query.one()
    assert row.status == "scored" and row.rule_version_id == entry.rule_version_id
    assert entry.material_record_id == row.id and str(entry.effective_score) == "5.0000"
    snapshot = StudentScoreSnapshot.query.one()
    assert str(snapshot.specialty_score) == "5.0000"
    assert batch.status == "stale"
    assert application.status == "approved" and application.final_score == 5
    assert student.academic_specialty_total == 5
    event = MaterialEvent.query.filter_by(action="reviewed").one()
    assert event.details["scoring"]["scoring"]["score_entry_id"] == entry.id


def test_scoring_failure_rolls_back_review_and_all_side_effects(env, monkeypatch):
    row, admin, batch, application, student = _setup(env)
    import use_cases.scoring as scoring

    monkeypatch.setattr(
        scoring,
        "rebuild_student_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("injected")),
    )
    with pytest.raises(RuntimeError, match="injected"):
        review_material(admin, row, 2, "verified", "核验通过", "failed-review")
    db.session.rollback()
    db.session.refresh(row)
    db.session.refresh(batch)
    assert row.status == "submitted" and batch.status == "draft"
    assert ScoreEntry.query.count() == 0
    assert StudentScoreSnapshot.query.count() == 0
    assert MaterialReviewCommand.query.count() == 0
    assert MaterialEvent.query.filter_by(action="reviewed").count() == 0
    db.session.refresh(application); db.session.refresh(student)
    assert application.status == "draft" and application.final_score is None
    assert student.academic_specialty_total is None


def test_ranking_invalidation_failure_rolls_back_override_and_projections(env, monkeypatch):
    row, admin, batch, application, student = _setup(env)
    import use_cases.scoring as scoring
    monkeypatch.setattr(
        scoring, "mark_draft_rankings_stale",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("ranking injected")),
    )
    with pytest.raises(RuntimeError, match="ranking injected"):
        review_material(
            admin, row, 2, "verified", "核验通过", "ranking-failed",
            override_score=4, override_reason="人工调整",
        )
    db.session.rollback()
    for item in (row, batch, application, student):
        db.session.refresh(item)
    assert row.status == "submitted" and batch.status == "draft"
    assert application.status == "draft" and application.final_score is None
    assert student.academic_specialty_total is None
    assert ScoreEntry.query.count() == 0
    assert StudentScoreSnapshot.query.count() == 0
    assert ScoreOverrideAudit.query.count() == 0
    assert MaterialEvent.query.filter_by(action="reviewed").count() == 0

