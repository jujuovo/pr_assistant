from datetime import date

from extensions import db
from models import Application, Rule, Student
from use_cases.migration import legacy_reconciliation_report
from use_cases.scoring import adapt_legacy_application
from workflow_models import RuleVersion


def _legacy_data():
    student = Student.query.filter_by(student_id="S1").one()
    # Successful legacy projection is intentionally limited to noncompetition
    # categories; competition records must use MaterialRecord.
    rule = Rule(name="对账规则", type="academic", sub_type="research", score=2)
    db.session.add(rule)
    db.session.flush()
    snapshot = {"score": 2, "max_count": None}
    version = RuleVersion(
        rule_id=rule.id, version=1, status="published", snapshot=snapshot,
        digest=RuleVersion.canonical_digest(snapshot),
    )
    db.session.add(version)
    application = Application(
        student_id=student.student_id, student_name=student.student_name,
        faculty_id=student.faculty_id, department_id=student.department_id,
        major_id=student.major_id, application_type="academic",
        project_name="历史项目", award_date=date(2026, 1, 1),
        status="approved", final_score=2, rule_id=rule.id,
        cycle_code=2026,
    )
    db.session.add(application)
    db.session.flush()
    return student, application


def test_reconciliation_is_read_only_repeatable_and_reports_all_levels(env):
    student, application = _legacy_data()
    student.comprehensive_score = 66
    student.major_ranking = 2
    db.session.commit()
    before_counts = {
        table.name: db.session.query(table).count()
        for table in db.metadata.sorted_tables
    }

    first = legacy_reconciliation_report(2026, faculty_id=student.faculty_id)
    second = legacy_reconciliation_report(2026, faculty_id=student.faculty_id)
    after_counts = {
        table.name: db.session.query(table).count()
        for table in db.metadata.sorted_tables
    }

    assert first == second and before_counts == after_counts
    assert first["details"][0]["state"] == "approved_without_score_entry"
    assert first["issue_counts"]["approved_without_score_entry"] == 1
    assert first["issue_counts"]["missing_snapshot"] == 1
    assert first["issue_counts"]["legacy_summary_difference"] == 1
    assert first["students"][0]["bonus_delta"] == "-2.0000"
    assert first["ranking_scope"][0]["different"] is True
    assert first["blocking_difference_count"] == 3


def test_reconciliation_matches_imported_detail_and_student_total(env):
    student, application = _legacy_data()
    adapt_legacy_application(application)
    db.session.commit()

    report = legacy_reconciliation_report(2026, faculty_id=student.faculty_id)

    assert report["details"][0]["state"] == "matched"
    assert report["students"][0]["bonus_delta"] == "0.0000"
    assert report["details"][0]["application_id"] == application.id


def test_reconciliation_never_guesses_missing_cycle_from_award_date(env):
    student, application = _legacy_data()
    application.cycle_code = None
    db.session.commit()

    report = legacy_reconciliation_report(2026, faculty_id=student.faculty_id)

    detail = report["details"][0]
    assert detail["state"] == "missing_fixed_cycle"
    assert detail["candidate_cycle_code"] is None
    assert report["issue_counts"]["missing_fixed_cycle"] == 1
    assert report["manual_review"][0]["required_evidence"] == {
        "cycle_policy_version_id": None, "rule_version_id": None,
        "evidence_type": None, "evidence_reference": None, "confirmed_by": None,
    }
    assert report["manual_review"][0]["prohibited_inference"] == "award_date_year"
    assert report["release_blocks"][0]["application_id"] == application.id
    assert report["ranking_release_allowed"] is False


def _material(student, *, status):
    from material_models import MaterialRecord

    material = MaterialRecord(
        student_id=student.student_id, faculty_id=student.faculty_id,
        category="competition", year=2028, status=status,
        data={}, analysis={},
    )
    db.session.add(material)
    db.session.commit()
    return material


def test_abandoned_material_does_not_block_ranking_release(env):
    """学生已放弃的材料不计分，也不该阻断排名发布。

    原先对账遍历材料时没有排除 abandoned：任何一个学生撤掉的材料只要没有
    确认快照，就会让整个学院整年的排名永久无法发布。其余查询处
    （material_bp、use_cases/materials、competition_review 等）都排除它。
    """
    student = Student.query.filter_by(student_id="S1").one()
    _material(student, status="abandoned")

    report = legacy_reconciliation_report(2028, faculty_id=student.faculty_id)

    assert report["release_blocks"] == []
    assert report["ranking_release_allowed"] is True
    assert report["issue_counts"]["missing_confirmation_snapshot"] == 0


def test_material_without_confirmation_still_blocks_when_in_scope(env):
    """对照：仍参与计分的材料缺确认快照时，必须继续阻断。"""
    student = Student.query.filter_by(student_id="S1").one()
    _material(student, status="scored")

    report = legacy_reconciliation_report(2028, faculty_id=student.faculty_id)

    assert [block["code"] for block in report["release_blocks"]] == [
        "structured_material_unresolved"
    ]
    assert report["ranking_release_allowed"] is False
