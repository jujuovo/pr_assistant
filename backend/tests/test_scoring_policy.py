from decimal import Decimal

import pytest

from domain.scoring import ScoreRuleError, calculate_score


@pytest.mark.parametrize(
    ("snapshot", "coefficient", "raw", "adjusted", "effective", "capped"),
    [
        ({"score": 5}, 1, "5.0000", "5.0000", "5.0000", False),
        ({"score": "5"}, "0.5", "5.0000", "2.5000", "2.5000", False),
        ({"score": 5, "max_score": 3}, 1, "5.0000", "5.0000", "3.0000", True),
        ({"score": "1.23456", "max_score": "9"}, "2", "1.2346", "2.4691", "2.4691", False),
    ],
)
def test_score_calculation(snapshot, coefficient, raw, adjusted, effective, capped):
    result = calculate_score(snapshot, coefficient=coefficient)
    assert result.raw_score == Decimal(raw)
    assert result.adjusted_score == Decimal(adjusted)
    assert result.effective_score == Decimal(effective)
    assert result.capped is capped


def test_missing_rule_is_not_silently_scored_zero():
    with pytest.raises(ScoreRuleError) as error:
        calculate_score(None)
    assert error.value.code == "no_applicable_rule"


@pytest.mark.parametrize(
    ("snapshot", "coefficient"),
    [
        ({}, 1),
        ({"score": -1}, 1),
        ({"score": "NaN"}, 1),
        ({"score": True}, 1),
        ({"score": 1, "max_score": -1}, 1),
        ({"score": 1}, -1),
        ({"score": 1}, "Infinity"),
    ],
)
def test_invalid_rule_or_coefficient_is_rejected(snapshot, coefficient):
    with pytest.raises(ScoreRuleError):
        calculate_score(snapshot, coefficient=coefficient)

