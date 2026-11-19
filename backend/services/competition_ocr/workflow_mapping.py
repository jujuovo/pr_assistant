"""Adapt OCR suggestions to the current formal catalog without guessing policy facts."""
from workflow_models import CompetitionRulePackage, RecommendationCyclePolicy

FAMILIES = {"lanqiao": "lanqiao-cup", "computer-design": "computer-design",
            "challenge-cup": "challenge-cup-business-plan", "csp": "csp"}
AWARDS = {"特等奖": "first_or_above", "一等奖": "first_or_above", "二等奖": "second", "三等奖": "third",
          "金奖": "first_or_above", "银奖": "second", "铜奖": "third"}


def catalog_item(key, package=None):
    if package is None:
        policy = RecommendationCyclePolicy.query.filter_by(status="active").one_or_none()
        package = CompetitionRulePackage.query.filter_by(cycle_code=policy.cycle_code,
            scope_key="global", status="current").one_or_none() if policy else None
    matches = [item for item in (package.snapshot["catalog"] if package else [])
               if item["event_family"] == FAMILIES.get(key)]
    return (package, matches[0]) if len(matches) == 1 else (package, None)


def for_workflow(key, raw, package=None):
    if not raw:
        return raw
    if key == "software-design":
        return {**raw, "material_category": "competition_evidence", "manual_only": True,
                "warnings": [*raw["warnings"], "该赛事未纳入正式计分目录，仅进行人工核验"],
                "missing_fields": [name for name in ("competition_name", "award_level", "award_date")
                                   if not raw["data"].get(name)]}
    if key not in FAMILIES:
        return raw
    package, item = catalog_item(key, package)
    if item is None:
        if key == "csp":
            return raw  # Standalone authentication transcript, no competition score source.
        return {**raw, "material_category": "competition", "data": {}, "evidence": raw["data"],
                "missing_fields": ["competition_id", "project_name", "award_date", "level", "award", "event_year", "participation_mode"],
                "warnings": [*raw["warnings"], "当前周期尚无对应正式竞赛条目，请联系管理员配置规则包"]}
    evidence = raw["data"]
    data = {"competition_id": item["competition_id"], "evidence": evidence}
    if evidence.get("project_name"):
        data["project_name"] = evidence["project_name"]
    date = evidence.get("award_date") or evidence.get("test_date")
    if date:
        data["award_date"] = date
    if evidence.get("award_level") in AWARDS:
        data["award"] = AWARDS[evidence["award_level"]]
    required = list(package.snapshot["field_schema"]["required"])
    warnings = ["比赛级别、参赛方式及团队信息须学生确认，不根据赛区或名单人数推断"]
    if key == "csp":
        required.append("csp_percentile")
        warnings.append("CSP总成绩不能推算排名百分位，请另行填写并提交官方依据")
    return {**raw, "material_category": "competition", "data": data, "cycle_code": package.cycle_code,
            "rule_package_id": package.id, "warnings": warnings,
            "missing_fields": [name for name in required if data.get(name) in (None, "", [])],
            "provenance": {"evidence."+key: value for key,value in raw["provenance"].items()}}
