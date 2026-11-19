"""Map OCR facts into editable business suggestions without inferring policy levels."""
import re
from datetime import date
from services.materials.ocr_schemas import SOCIAL_REQUIRED

COMPETITIONS = {"lanqiao", "computer-design", "software-design", "challenge-cup"}
TARGETS = {
    **{key: ["competition"] for key in COMPETITIONS},
    "csp": ["competition", "certification"], "social-practice": ["social_practice"],
    "other": ["student_work", "research"], "software-design": ["competition_evidence"],
}
COMMON = {
    "event": "competition_name", "edition": "edition", "participants": "participants",
    "project": "project_name", "school": "school", "award": "award_level", "group": "group",
    "stage_as_printed": "stage_as_printed", "certificate_no": "certificate_no", "advisers": "advisers",
    "award_date": "award_date",
}
LANQIAO = {
    "school": "school", "student": "participants", "teacher": "advisers", "edition": "edition",
    "track": "track", "group": "group", "region": "region", "award": "award_level",
    "certificate_no": "certificate_no", "date": "award_date",
}
CSP = {
    "document_type": "document_type",
    "name": "subject_name", "certificate_no": "certificate_no", "test_date": "test_date",
    "batch": "batch", "language": "language", "test_site": "test_site",
    "task_scores": "task_scores", "total_score": "score",
}


def normalized_date(value):
    if not isinstance(value, str):
        return None
    found = re.fullmatch(r"(\d{4})[年./-](\d{1,2})[月./-](\d{1,2})日?", value)
    try:
        return date(*map(int, found.groups())).isoformat() if found else None
    except ValueError:
        return None


def raw_suggestions(key, report):
    if not report or not isinstance(report.get("fields"), dict):
        return None
    fields, warnings, provenance = report["fields"], [], {}
    if key in COMPETITIONS:
        target, rules = "competition", LANQIAO if key == "lanqiao" else COMMON
        data = {"project_key": key}
        if key == "lanqiao":
            data["competition_name"] = "蓝桥杯"
        required = ["competition_name", "organizer", "competition_level", "award_level", "award_date"]
        warnings.append("比赛级别和主办单位须由学生补充并由教师核验，赛段文字不代替级别")
    elif key == "csp":
        target, rules = "certification", CSP
        data = {"certification_name": "CCF CSP"}
        required = ["certification_name", "score", "full_score", "test_date", "certificate_no"]
        warnings.append("认证满分须确认；认证成绩不转换成竞赛奖项")
    elif key == "social-practice":
        target, rules = "social_practice", {name: name for name in fields}
        data = {}
        required = ["document_type", *SOCIAL_REQUIRED.get(fields.get("document_type"), ())]
    elif key == "other" and fields.get("document_type") == "appointment_proof":
        return _appointment(fields)
    elif key == "other" and fields.get("document_type") == "research_report":
        target, rules, data = "research", {name: name for name in fields}, {}
        required = ["document_type", "report_no", "database"]
    else:
        return {"material_category": None, "data": {}, "missing_fields": [],
                "warnings": ["未匹配到业务字段，请人工选择材料类型"], "provenance": {}, "unmapped_fields": list(fields)}
    for source, destination in rules.items():
        value = fields.get(source)
        if key == "lanqiao" and destination in ("participants", "advisers"):
            value = [value] if value else []
        if destination in ("award_date", "test_date", "issue_date", "honor_date"):
            value = normalized_date(value)
        if value not in (None, "", []):
            data[destination] = value
            provenance[destination] = source
    return {"material_category": target, "data": data,
            "missing_fields": [name for name in required if data.get(name) in (None, "", [])],
            "warnings": warnings, "provenance": provenance,
            "unmapped_fields": [name for name in fields if name not in rules]}


def _appointment(fields):
    role = {key: fields.get(key) for key in ("organization", "position")}
    data = {"subject_name": fields.get("name") or "",
            "start_month_as_printed": fields.get("start_month") or "",
            "end_month_as_printed": fields.get("end_month") or "",
            "appointments": [{**role, "position_level": None, "start_date": None, "end_date": None,
                              "assessment_result": None}]}
    missing = ["as_of", "appointments[0].position_level", "appointments[0].start_date", "appointments[0].end_date", "appointments[0].assessment_result"]
    missing.extend("appointments[0]." + key for key, value in role.items() if not value)
    return {"material_category": "student_work", "data": data, "missing_fields": missing,
            "warnings": ["任期只识别到年月，不虚构具体日期；结束日期留空表示仍在任，须学生确认"],
            "provenance": {**{f"appointments[0].{key}": key for key in role},
                           "subject_name": "name", "start_month_as_printed": "start_month", "end_month_as_printed": "end_month"},
            "source_hints": {key: fields.get(key) for key in ("name", "start_month", "end_month")},
            "unmapped_fields": ["document_type"]}


def suggestions(key, report, package=None):
    from .workflow_mapping import for_workflow
    return for_workflow(key, raw_suggestions(key, report), package)
