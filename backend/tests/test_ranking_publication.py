from datetime import datetime
from decimal import Decimal

import pytest

from extensions import db
from models import Student, User
from material_models import MaterialRecord
from use_cases.ranking import (
    RankingUseCaseError, create_successor_draft, freeze_ranking_batch, generate_ranking_draft,
    publish_ranking_batch, withdraw_ranking_batch,
)
from use_cases.scoring import mark_draft_rankings_stale
from workflow_models import StudentScoreSnapshot


def _draft(env):
    student = Student.query.filter_by(student_id="S1").one()
    db.session.add(StudentScoreSnapshot(
        student_id="S1", faculty_id=student.faculty_id, year=2026, version=1,
        status="current", academic_base_score=80, academic_weight=80,
        specialty_raw_score=5, specialty_score=5, performance_raw_score=1,
        performance_score=1, comprehensive_score=70, input_digest="a"*64,
        rule_version_ids=[], breakdown=[]))
    db.session.commit()
    batch,_=generate_ranking_draft(2026,student.faculty_id,major_id=student.major_id,
        cutoff_at=datetime(2030,1,1),created_by=env[2]["admin"])
    db.session.commit()
    return student,batch,db.session.get(User,env[2]["admin"])


def test_freeze_blocks_permission_stale_and_reconciliation(env):
    student,batch,admin=_draft(env)
    other=db.session.get(User,env[2]["other"])
    with pytest.raises(RankingUseCaseError) as error: freeze_ranking_batch(other,batch,1)
    assert error.value.code=="forbidden"
    with pytest.raises(RankingUseCaseError) as error: freeze_ranking_batch(admin,batch,1,unresolved_differences=1)
    assert error.value.code=="reconciliation_blocked"
    mark_draft_rankings_stale(student,2026,"score changed")
    db.session.commit()
    with pytest.raises(RankingUseCaseError): freeze_ranking_batch(admin,batch,batch.version)


def test_freeze_automatically_blocks_unconfirmed_material(env):
    student,batch,admin=_draft(env)
    db.session.add(MaterialRecord(student_id=student.student_id, faculty_id=student.faculty_id,
        category="honor", year=batch.year, status="submitted", data={}, analysis={}))
    db.session.commit()
    with pytest.raises(RankingUseCaseError) as error:
        freeze_ranking_batch(admin,batch,1)
    assert error.value.code == "reconciliation_blocked"


def test_published_batch_is_immutable_to_draft_invalidation_and_can_be_withdrawn(env):
    student,batch,admin=_draft(env)
    freeze_ranking_batch(admin,batch,1); publish_ranking_batch(admin,batch,2); db.session.commit()
    published_at=batch.published_at
    assert mark_draft_rankings_stale(student,2026,"later score change")==[]
    assert batch.status=="published" and batch.published_at==published_at
    withdraw_ranking_batch(admin,batch,3,"审核错误"); db.session.commit()
    assert batch.status=="withdrawn" and batch.withdrawal_reason=="审核错误"


def test_withdrawn_batch_requires_changed_inputs_for_successor(env):
    student,batch,admin=_draft(env)
    freeze_ranking_batch(admin,batch,1); publish_ranking_batch(admin,batch,2)
    withdraw_ranking_batch(admin,batch,3,"审核错误"); db.session.commit()
    with pytest.raises(RankingUseCaseError):
        create_successor_draft(admin,batch)
    current=StudentScoreSnapshot.query.filter_by(student_id="S1",status="current").one()
    current.status="superseded"
    db.session.add(StudentScoreSnapshot(
        student_id="S1",faculty_id=student.faculty_id,year=2026,version=2,status="current",
        academic_base_score=80,academic_weight=80,specialty_raw_score=6,specialty_score=6,
        performance_raw_score=1,performance_score=1,comprehensive_score=71,input_digest="b"*64,
        rule_version_ids=[],breakdown=[]))
    db.session.commit()
    successor=create_successor_draft(admin,batch); db.session.commit()
    assert successor.status=="draft" and successor.predecessor_batch_id==batch.id
    assert successor.input_digest!=batch.input_digest

