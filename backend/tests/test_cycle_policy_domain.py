from datetime import date

import pytest

from domain.cycles import CyclePolicyError, evaluate_award_date, normalize_cycle_code


def test_cycle_code_is_a_four_digit_integer_year():
    assert normalize_cycle_code(2026) == 2026
    assert normalize_cycle_code("2026") == 2026
    for invalid in (None, True, "2025-2026", 1999, 2101, "02026"):
        with pytest.raises(CyclePolicyError):
            normalize_cycle_code(invalid)


def test_award_window_is_inclusive_and_explains_outcomes():
    start, end = date(2023, 9, 1), date(2026, 8, 31)
    assert evaluate_award_date(start, start, end).eligible
    assert evaluate_award_date(end, start, end).eligible
    outside = evaluate_award_date(date(2023, 8, 31), start, end)
    assert outside.status == "not_eligible"
    assert outside.reason == "award_date_outside_cycle_window"
    assert evaluate_award_date(None, start, end).status == "needs_correction"


def test_invalid_award_window_is_rejected():
    with pytest.raises(CyclePolicyError, match="end precedes start"):
        evaluate_award_date(date(2026, 1, 1), date(2026, 2, 1), date(2026, 1, 1))
