"""Read-only ranking reconciliation against the material workflow."""
from collections import defaultdict

from domain.structured_rules import RuleCandidate, evaluate_candidate
from extensions import db
from material_models import MaterialRecord
from models import Student
from workflow_models import RuleVersion


def material_issues(year, faculty_id=None):
    query = Student.query
    if faculty_id is not None:
        query = query.filter_by(faculty_id=faculty_id)
    students = {student.student_id: student for student in query}
    issue_counts = defaultdict(int)
    material_rows = []
    material_issue_keys = (
        "evidence_date_conflict", "missing_confirmation_snapshot",
        "uncovered_structured_terms", "ambiguous_structured_rules",
        "incorrect_default_rule",
    )
    material_query = MaterialRecord.query.order_by(MaterialRecord.id)
    if faculty_id is not None:
        material_query = material_query.filter_by(faculty_id=faculty_id)
    # 学生已放弃的材料既不计分也不属于待处理工作，不应阻断排名发布。
    # 其余查询处（material_bp、use_cases/materials、use_cases/competition_review、
    # services/materials/service）同样把 abandoned 排除在外，这里保持一致。
    material_query = material_query.filter(MaterialRecord.status != "abandoned")
    for material in material_query.all():
        if material.cycle_policy_version_id is not None and material.year != year:
            continue
        issues = []
        confirmed = material.confirmed_terms if isinstance(material.confirmed_terms, dict) else None
        normalized = material.normalized_terms if isinstance(material.normalized_terms, dict) else None
        ocr = material.ocr_raw_terms if isinstance(material.ocr_raw_terms, dict) else None
        saved_date = (material.data or {}).get("award_date")
        confirmed_date = (normalized or {}).get("award_date")
        ocr_date = (ocr or {}).get("award_date") or (ocr or {}).get("date")
        if not confirmed or not normalized:
            issues.append("missing_confirmation_snapshot")
        if confirmed_date and saved_date and confirmed_date != saved_date:
            issues.append("evidence_date_conflict")
        elif ocr_date and confirmed_date and ocr_date != confirmed_date:
            issues.append("evidence_date_conflict")
        if material.status == "rule_unmatched":
            issues.append("uncovered_structured_terms")
        if normalized:
            try:
                from use_cases.materials import match_material_rule
                match = match_material_rule(material, year)
                if match["status"] == "ambiguous":
                    issues.append("ambiguous_structured_rules")
            except ValueError:
                pass
        if material.rule_version_id and normalized:
            bound = db.session.get(RuleVersion, material.rule_version_id)
            snapshot = bound.snapshot if bound else {}
            terms = snapshot.get("match_terms")
            if isinstance(terms, dict):
                candidate = RuleCandidate(
                    version_id=bound.id, cycle_code=snapshot.get("cycle_code"),
                    faculty_id=snapshot.get("faculty_id"),
                    material_category=snapshot.get("sub_type"), terms=terms,
                    score=snapshot.get("score"),
                )
                matched, _explanation = evaluate_candidate(
                    candidate, cycle_code=year, faculty_id=material.faculty_id,
                    material_category=material.category, terms=normalized,
                )
                if not matched:
                    issues.append("incorrect_default_rule")
        issues = list(dict.fromkeys(issues))
        for issue in issues:
            issue_counts[issue] += 1
        if issues:
            student = students.get(material.student_id)
            material_rows.append({
                "material_record_id": material.id,
                "student_id": material.student_id,
                "issues": issues,
                "ocr_award_date": ocr_date,
                "confirmed_award_date": confirmed_date,
                "saved_award_date": saved_date,
                "bound_rule_version_id": material.rule_version_id,
                "affected_ranking_scope": {
                    "year": year, "faculty_id": material.faculty_id,
                    "major_id": student.major_id if student else None,
                },
            })
    return material_rows, {key: issue_counts[key] for key in material_issue_keys}
