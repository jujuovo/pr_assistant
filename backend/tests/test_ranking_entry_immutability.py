from datetime import datetime

import pytest

from extensions import db
from use_cases.ranking import (
    create_corrected_draft, freeze_ranking_batch, request_ranking_correction,
)
from workflow_models import RankingEntry, StudentScoreSnapshot
from test_ranking_publication import _draft


def test_ranking_entry_cannot_be_edited_directly(env):
    student, batch, admin = _draft(env)
    entry = RankingEntry.query.filter_by(batch_id=batch.id).one()
    entry.rank = 99
    with pytest.raises(ValueError, match="immutable"):
        db.session.flush()
    db.session.rollback(); entry = db.session.get(RankingEntry, entry.id)
    assert entry.rank == 1


def test_correction_requires_authority_change_and_records_source_summary(env):
    student, batch, admin = _draft(env)
    freeze_ranking_batch(admin, batch, 1)
    request_ranking_correction(admin, batch, 2, "快照来源错误")
    db.session.commit()
    with pytest.raises(Exception) as unchanged:
        create_corrected_draft(admin, batch)
    assert getattr(unchanged.value, "code", None) == "authoritative_source_unchanged"
    db.session.rollback(); batch = db.session.get(type(batch), batch.id)
    old = StudentScoreSnapshot.query.filter_by(student_id="S1", status="current").one()
    old.status = "superseded"
    db.session.add(StudentScoreSnapshot(
        student_id="S1", faculty_id=student.faculty_id, year=2026, version=2,
        status="current", academic_base_score=80, academic_weight=80,
        specialty_raw_score=7, specialty_score=7, performance_raw_score=1,
        performance_score=1, comprehensive_score=72, input_digest="q" * 64,
        rule_version_ids=[], breakdown=[],
    )); db.session.commit()
    successor = create_corrected_draft(admin, batch); db.session.commit()
    assert successor.status == "draft" and successor.predecessor_batch_id == batch.id
    assert successor.source_summary == {
        "batch_id": batch.id, "status": "correction_required", "version": 3,
        "input_digest": batch.input_digest, "correction_reason": "快照来源错误",
    }
    assert successor.input_digest != batch.input_digest
