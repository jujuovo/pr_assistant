"""Business fields for recognized documents that do not belong to the original five types."""
from decimal import Decimal

STRING_ARRAYS = {"participants", "advisers", "members", "teams"}
NUMBER_ARRAYS = {"task_scores"}
ARRAY_FIELDS = STRING_ARRAYS | NUMBER_ARRAYS
COMPETITION_PROJECTS = ("manual", "lanqiao", "computer-design", "software-design", "challenge-cup")
MANUAL_TYPES = {"competition_evidence", "certification", "social_practice", "research", "arts_sports"}
ARTS_SPORTS_TYPES = {
    "arts_competition": "文体竞赛",
    "performance": "表演展示",
    "arts_honor": "文体表彰",
    "dorm_honor": "文明宿舍表彰",
    "fitness_test": "体质健康测试",
}
NEW_TYPES = {
    "competition_evidence": {
        "name": "目录外竞赛材料", "fields": ["competition_name", "organizer", "competition_level", "award_level",
            "award_date", "certificate_no", "project_key", "reference_id", "project_name", "participants",
            "advisers", "school", "edition", "track", "group", "region", "stage_as_printed"],
        "required": ["competition_name", "award_level", "award_date"],
        "non_ocr": ["目录外材料仅人工核验", "不生成计分记录，不扩充正式赛事目录"]},
    "certification": {
        "name": "能力认证", "fields": ["document_type", "certification_name", "subject_name", "score", "full_score", "test_date",
            "certificate_no", "batch", "language", "test_site", "task_scores", "reference_id"],
        "required": ["certification_name", "score", "full_score", "test_date", "certificate_no"],
        "non_ocr": ["认证成绩与题分校验", "官方核验结果记录"]},
    "social_practice": {
        "name": "社会实践", "fields": ["document_type", "team", "teams", "period_as_printed", "issuer",
            "members", "issue_date", "submitter", "honor_name", "practice", "honor_description",
            "honor_date", "review_status_as_printed", "reference_id"],
        "required": ["document_type"], "non_ocr": ["实践证明、平台截图、名单分别核验", "不据队名推断个人参与"]},
    "research": {
        "name": "成果检索证明", "fields": ["document_type", "report_no", "requester_school", "database",
            "publication_year", "reference_id"],
        "required": ["document_type", "report_no", "database"],
        "non_ocr": ["检索依据人工核验", "不推断论文归属或分区"]},
}
SOCIAL_REQUIRED = {
    "practice_proof": ("team", "period_as_printed"),
    "platform_screenshot": ("submitter", "honor_name", "honor_date"),
    "team_list": ("teams",),
}


def normalize_extra(category, data, result, spec, text, numeric):
    for key in set(spec["fields"]) & ARRAY_FIELDS & set(data):
        values = data[key]
        if not isinstance(values, list) or len(values) > 300:
            raise ValueError(f"{key}必须为最多300项的数组")
        result[key] = ([text(value, key) for value in values] if key in STRING_ARRAYS else
                       [numeric(value, key, high=Decimal("100")) for value in values])
    if category == "certification":
        result["score"] = numeric(data["score"], "认证成绩")
        result["full_score"] = numeric(data["full_score"], "认证满分", positive=True)
        if Decimal(result["score"]) > Decimal(result["full_score"]):
            raise ValueError("认证成绩不能超过满分")
        scores = result.get("task_scores")
        if scores is not None and (len(scores) != 5 or sum(map(Decimal, scores)) != Decimal(result["score"])):
            raise ValueError("CSP五道题分必须与总成绩一致")
    if category == "social_practice":
        kind = result["document_type"]
        if kind not in SOCIAL_REQUIRED:
            raise ValueError("社会实践材料类型无效")
        for key in SOCIAL_REQUIRED[kind]:
            if not result.get(key):
                raise ValueError(f"社会实践缺少字段：{key}")
    if category == "research" and result["document_type"] != "research_report":
        raise ValueError("成果证明类型无效")
    if category == "arts_sports":
        if result.get("document_type") not in ARTS_SPORTS_TYPES:
            raise ValueError("文体活动提交项无效")
        project_name = result.get("project_name") or ""
        if not 2 <= len(project_name) <= 30:
            raise ValueError("项目名称必须为2-30个字符")
