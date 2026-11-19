from datetime import datetime

import pytest

from extensions import db
from models import Student, User
from use_cases.ranking import RankingUseCaseError, freeze_ranking_batch, ranking_freeze_blockers
from workflow_models import RankingBatch, RankingEntry, StudentScoreSnapshot


def make_batch(env, *, snapshot=True, eligible=True, status="draft"):
    student = Student.query.filter_by(student_id="S1").one()
    score = None
    if snapshot:
        score = StudentScoreSnapshot(
            student_id="S1", faculty_id=student.faculty_id, year=2026, version=1,
            status="current", academic_base_score=80, academic_weight=80,
            specialty_raw_score=5, specialty_score=5, performance_raw_score=1,
            performance_score=1, comprehensive_score=70, input_digest="z" * 64,
            rule_version_ids=[11], breakdown=[],
        )
        db.session.add(score); db.session.flush()
    batch = RankingBatch(
        year=2026, faculty_id=student.faculty_id, major_id=student.major_id,
        scope_type="major", scope_definition={"major_id": student.major_id},
        cutoff_at=datetime(2030, 1, 1), rule_version_ids=[11], score_precision=4,
        status=status, version=1, input_digest="y" * 64, created_by=env[2]["admin"],
        stale_reason="score changed" if status == "stale" else None,
    )
    db.session.add(batch); db.session.flush()
    db.session.add(RankingEntry(
        batch_id=batch.id, student_id="S1", score_snapshot_id=score.id if score else None,
        frozen_score=70 if score else None, rank=1 if eligible else None,
        display_order=1, eligible=eligible,
        exclusion_reason=None if eligible else "missing_score_snapshot",
    )); db.session.commit()
    return batch, db.session.get(User, env[2]["admin"])


@pytest.mark.parametrize("snapshot,eligible,expected", [
    (False, False, {"eligibility", "snapshot"}),
    (False, True, {"snapshot"}),
])
def test_freeze_returns_locatable_snapshot_and_eligibility_blockers(env, snapshot, eligible, expected):
    batch, admin = make_batch(env, snapshot=snapshot, eligible=eligible)
    before = (batch.status, batch.version)
    with pytest.raises(RankingUseCaseError) as error:
        freeze_ranking_batch(admin, batch, 1)
    assert {item["type"] for item in error.value.details} == expected
    assert all(item.get("student_id") == "S1" for item in error.value.details)
    assert (batch.status, batch.version) == before


def test_stale_input_and_rule_version_mismatch_block_entire_freeze(env):
    batch, admin = make_batch(env)
    batch.rule_version_ids = []
    current = StudentScoreSnapshot.query.one(); current.status = "superseded"
    db.session.add(StudentScoreSnapshot(
        student_id="S1", faculty_id=current.faculty_id, year=2026, version=2,
        status="current", academic_base_score=80, academic_weight=80,
        specialty_raw_score=6, specialty_score=6, performance_raw_score=1,
        performance_score=1, comprehensive_score=71, input_digest="x" * 64,
        rule_version_ids=[12], breakdown=[],
    )); db.session.commit()
    blockers = ranking_freeze_blockers(batch)
    assert {item["type"] for item in blockers} >= {"stale_input", "rule_version"}
    with pytest.raises(RankingUseCaseError):
        freeze_ranking_batch(admin, batch, 1)
    assert batch.status == "draft" and batch.version == 1
