"""Confirmed certificate details are evidence, never scoring authority."""
from decimal import Decimal, InvalidOperation

TEXT_FIELDS = {
    "document_type", "subject_name", "school", "edition", "track", "group", "region",
    "award_level", "award_date", "certificate_no", "competition_name", "organizer", "project_key",
    "project_name", "certification_name", "test_date", "batch", "language", "test_site", "stage_as_printed",
}
LIST_FIELDS = {"participants", "advisers"}
NUMBER_FIELDS = {"score", "full_score"}


def _text(value):
    if not isinstance(value, str) or len(value) > 200 or any(
        ord(c) == 0 or 0xD800 <= ord(c) <= 0xDFFF for c in value
    ):
        raise ValueError("证书补充字段必须为200字以内文字")
    return value.strip()


def _number(value, maximum=1000000):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)) or len(str(value)) > 40:
        raise ValueError("证书成绩必须为有效数值")
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("证书成绩必须为有效数值") from None
    if not result.is_finite() or not 0 <= result <= maximum or result.as_tuple().exponent < -8:
        raise ValueError("证书成绩超出有效范围")
    return format(result.normalize(), "f")


def normalize_evidence(data):
    if not isinstance(data, dict) or set(data) - TEXT_FIELDS - LIST_FIELDS - NUMBER_FIELDS - {"task_scores"}:
        raise ValueError("不支持的证书补充字段")
    result = {}
    for key, value in data.items():
        if key in LIST_FIELDS or key == "task_scores":
            if not isinstance(value, list) or len(value) > 300:
                raise ValueError("证书名单必须为不超过300项的数组")
            result[key] = [_number(v, 100) if key == "task_scores" else _text(v) for v in value]
        else:
            result[key] = _number(value) if key in NUMBER_FIELDS else _text(value)
    if "full_score" in result and "score" in result and Decimal(result["score"]) > Decimal(result["full_score"]):
        raise ValueError("认证成绩不能超过满分")
    if "task_scores" in result and (len(result["task_scores"]) != 5 or
        ("score" in result and sum(map(Decimal, result["task_scores"])) != Decimal(result["score"]))):
        raise ValueError("CSP五题成绩必须与总成绩一致")
    return result
