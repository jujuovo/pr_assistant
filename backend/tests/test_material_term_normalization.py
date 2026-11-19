import pytest

from domain.material_terms import (
    NORMALIZATION_VERSION, TermNormalizationError,
    normalize_confirmed_terms, normalize_date, normalize_term,
)


def test_chinese_and_iso_dates_normalize_to_iso():
    assert normalize_date("2026年5月8日") == "2026-05-08"
    assert normalize_date(" 2026-5-8 ") == "2026-05-08"
    assert normalize_date("2026-05-08") == "2026-05-08"
    assert normalize_date("") is None
    assert NORMALIZATION_VERSION == "material-terms-v1"


@pytest.mark.parametrize("value,reason", [
    ("2026/05/08", "unrecognized_date"),
    ("2026年2月30日", "invalid_date"),
    ("五月八日", "unrecognized_date"),
])
def test_invalid_or_unrecognized_dates_are_not_guessed(value, reason):
    with pytest.raises(TermNormalizationError) as error:
        normalize_date(value)
    assert error.value.field == "award_date"
    assert error.value.reason == reason


def test_controlled_aliases_and_unknown_terms_are_deterministic():
    assert normalize_term("competition_name", "全国软件和信息技术专业人才大赛") == "蓝桥杯"
    assert normalize_term("award_level", "三等 奖") == "三等奖"
    assert normalize_term("competition_level", "省赛") == "省级"
    assert normalize_term("group", " 软件类大学 B 组 ") == "软件类大学B组"
    assert normalize_term("track", None) is None


def test_confirmed_terms_have_stable_shape_and_ignore_uncontrolled_keys():
    result = normalize_confirmed_terms({
        "competition_name": "蓝桥杯", "award_level": "三等奖",
        "competition_level": "省级", "region": "福建赛区",
        "group": "软件类大学B组", "track": "Python",
        "award_date": "2026年5月8日", "ocr_only": "must not propagate",
    })
    assert result == {
        "competition_name": "蓝桥杯", "award_level": "三等奖",
        "competition_level": "省级", "region": "福建赛区",
        "group": "软件类大学B组", "track": "Python",
        "award_date": "2026-05-08",
    }
