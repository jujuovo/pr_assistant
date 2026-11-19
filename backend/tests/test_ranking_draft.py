from datetime import datetime
from decimal import Decimal

from extensions import db
from models import Student
from use_cases.ranking import generate_ranking_draft
from use_cases.scoring import mark_draft_rankings_stale
from workflow_models import RankingBatch, RankingEntry, StudentScoreSnapshot


def _snapshot(student, score, digest):
    row = StudentScoreSnapshot(
        student_id=student.student_id, faculty_id=student.faculty_id, year=2026,
        version=1, status="current", academic_base_score=student.academic_score,
        academic_weight=80, specialty_raw_score=5, specialty_score=5,
        performance_raw_score=1, performance_score=1, comprehensive_score=score,
        input_digest=digest, rule_version_ids=[], breakdown=[],
    )
    db.session.add(row)
    return row


def test_generate_draft_is_deterministic_and_persists_entries(env):
    student = Student.query.filter_by(student_id="S1").one()
    _snapshot(student, Decimal("70"), "a" * 64)
    db.session.commit()
    cutoff = datetime(2030, 1, 1)
    first, created = generate_ranking_draft(
        2026, student.faculty_id, major_id=student.major_id,
        cutoff_at=cutoff, created_by=env[2]["admin"],
    )
    db.session.commit()
    second, created_again = generate_ranking_draft(
        2026, student.faculty_id, major_id=student.major_id,
        cutoff_at=cutoff, created_by=env[2]["admin"],
    )
    db.session.commit()
    assert created and not created_again and first.id == second.id
    assert RankingEntry.query.one().rank == 1


def test_score_change_stales_only_matching_major_scope(env):
    student = Student.query.filter_by(student_id="S1").one()
    _snapshot(student, Decimal("70"), "a" * 64)
    db.session.commit()
    cutoff = datetime(2030, 1, 1)
    matching, _ = generate_ranking_draft(
        2026, student.faculty_id, major_id=student.major_id,
        cutoff_at=cutoff, created_by=env[2]["admin"],
    )
    unrelated = RankingBatch(
        year=2026, faculty_id=student.faculty_id, major_id=999,
        scope_type="major", scope_definition={"major_id": 999}, cutoff_at=cutoff,
        rule_version_ids=[], score_precision=4, status="draft", version=1,
        input_digest="b" * 64, created_by=env[2]["admin"],
    )
    db.session.add(unrelated)
    db.session.commit()
    changed = mark_draft_rankings_stale(student, 2026, "score changed")
    db.session.commit()
    assert [batch.id for batch in changed] == [matching.id]
    assert matching.status == "stale" and matching.stale_reason == "score changed"
    assert unrelated.status == "draft"

