"""Normalization of student-confirmed evidence terms.

OCR text is intentionally not accepted here.  Callers must pass the values the
student confirmed; this module only makes those values deterministic for rule
matching and auditing.
"""
import re
import unicodedata
from datetime import date


NORMALIZATION_VERSION = "material-terms-v1"
TERM_FIELDS = (
    "competition_name", "award_level", "competition_level",
    "region", "group", "track", "award_date",
)


class TermNormalizationError(ValueError):
    def __init__(self, field, reason):
        self.field = field
        self.reason = reason
        super().__init__(f"{field}: {reason}")


def _text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise TermNormalizationError("terms", "value_must_be_text")
    value = unicodedata.normalize("NFKC", value).strip()
    value = re.sub(r"\s+", "", value)
    return value or None


ALIASES = {
    "competition_name": {
        "蓝桥杯": "蓝桥杯",
        "全国软件和信息技术专业人才大赛": "蓝桥杯",
        "蓝桥杯全国软件和信息技术专业人才大赛": "蓝桥杯",
    },
    "award_level": {
        "一等": "一等奖", "一等奖": "一等奖",
        "二等": "二等奖", "二等奖": "二等奖",
        "三等": "三等奖", "三等奖": "三等奖",
        "优秀奖": "优秀奖",
    },
    "competition_level": {
        "国家级": "国家级", "全国": "国家级", "全国级": "国家级",
        "省级": "省级", "省赛": "省级",
        "校级": "校级", "校赛": "校级",
    },
}


def normalize_date(value):
    value = _text(value)
    if value is None:
        return None
    match = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", value)
    if match:
        parts = tuple(int(item) for item in match.groups())
    else:
        match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
        if not match:
            raise TermNormalizationError("award_date", "unrecognized_date")
        parts = tuple(int(item) for item in match.groups())
    try:
        return date(*parts).isoformat()
    except ValueError as error:
        raise TermNormalizationError("award_date", "invalid_date") from error


def normalize_term(field, value):
    if field == "award_date":
        return normalize_date(value)
    value = _text(value)
    if value is None:
        return None
    return ALIASES.get(field, {}).get(value, value)


def normalize_confirmed_terms(terms):
    if not isinstance(terms, dict):
        raise TermNormalizationError("terms", "object_required")
    return {
        field: normalize_term(field, terms.get(field))
        for field in TERM_FIELDS
    }
