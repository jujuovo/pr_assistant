from datetime import datetime
from decimal import Decimal

from extensions import db
from models import Student
from use_cases.ranking import select_ranking_candidates
from workflow_models import StudentScoreSnapshot


def _snapshot(student, score="70"):
    snapshot = StudentScoreSnapshot(
        student_id=student.student_id,
        faculty_id=student.faculty_id,
        year=2026,
        version=1,
        status="current",
        academic_base_score=Decimal(str(student.academic_score or 0)),
        academic_weight=Decimal("80"),
        specialty_raw_score=Decimal("6"),
        specialty_score=Decimal("5"),
        performance_raw_score=Decimal("1"),
        performance_score=Decimal("1"),
        comprehensive_score=Decimal(score),
        input_digest=(student.student_id[-1] * 64),
        rule_version_ids=[],
        breakdown=[],
    )
    db.session.add(snapshot)
    return snapshot


def test_scope_and_missing_data_are_explicit(env):
    first = Student.query.filter_by(student_id="S1").one()
    second = Student(
        student_id="S2", student_name="李四", faculty_id=first.faculty_id,
        department_id=first.department_id, major_id=first.major_id, academic_score=None,
    )
    third = Student(
        student_id="S3", student_name="王五", faculty_id=first.faculty_id,
        department_id=first.department_id, major_id=first.major_id, academic_score=75,
    )
    db.session.add_all([second, third])
    _snapshot(first)
    db.session.commit()
    candidates = select_ranking_candidates(2026, first.faculty_id, major_id=first.major_id)
    by_student = {item.student_id: item for item in candidates}
    assert by_student["S1"].eligible
    assert by_student["S2"].exclusion_reason == "missing_academic_score"
    assert by_student["S3"].exclusion_reason == "missing_score_snapshot"


def test_cutoff_excludes_late_snapshot(env):
    student = Student.query.filter_by(student_id="S1").one()
    snapshot = _snapshot(student)
    db.session.commit()
    candidates = select_ranking_candidates(
        2026, student.faculty_id, major_id=student.major_id,
        cutoff_at=datetime(2000, 1, 1),
    )
    assert candidates[0].eligible is False
    assert candidates[0].exclusion_reason == "missing_score_snapshot"

