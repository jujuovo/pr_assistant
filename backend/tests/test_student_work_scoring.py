from decimal import Decimal
import pytest
from domain.student_work_scoring import candidate
from services.materials.schemas import normalize_student_work


def assessment(**changes):
    return dict(appointment_index=0, academic_year=2025, scope="college", mapped_position="院学生会主席团成员",
                mapping_basis="任职证明第一条", tenure="full_year", tenure_basis="指导老师证明完整学年",
                assessment_score=80, assessor_role="辅导员", assessment_source="签章考核表",
                proof_date="2028-08-31") | changes


@pytest.mark.parametrize("changes,expected", [({}, "1.2"), ({"tenure":"semester"}, "0.6"),
    ({"tenure":"below_semester"}, "0"), ({"assessment_score":0}, "0"), ({"proof_date":"2028-09-01"}, "0"),
    ({"mapped_position":"社团社长"}, "0.6"), ({"mapped_position":"辩论队队长"}, "0.4"),
    ({"scope":"university","assessor_role":"指导老师"}, "1.2")])
def test_candidate(changes, expected):
    facts = normalize_student_work("student_work", {"assessments":[assessment(**changes)]})
    assert candidate("student_work", facts, "2028-08-31")[0] == Decimal(expected)


@pytest.mark.parametrize("changes", [{"assessment_score":101},{"assessment_score":-1},{"assessment_source":""},
    {"mapped_position":"未列岗位"},{"assessment_score":None},{"scope":"university"},{"academic_year":None}])
def test_unverified(changes):
    with pytest.raises(ValueError):
        normalize_student_work("student_work", {"assessments":[assessment(**changes)]})


def test_cross_year_appointment_requires_each_annual_assessment():
    first = assessment()
    second = assessment(academic_year=2026, assessment_score=60, assessment_source="次学年签章考核表")
    facts = normalize_student_work("student_work", {"assessments": [first, second]})
    total, rows = candidate("student_work", facts, "2028-08-31")
    assert total == Decimal("2.1")
    assert [Decimal(row["candidate"]) for row in rows] == [Decimal("1.2"), Decimal("0.9")]
    del second["assessment_source"]
    with pytest.raises(ValueError, match="assessment_source"):
        normalize_student_work("student_work", {"assessments": [first, second]})
