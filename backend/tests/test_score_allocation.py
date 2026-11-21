from decimal import Decimal

from domain.scoring import ScoreCandidate, allocate_candidates


def _result(candidates):
    return {
        item.entry_id: (item.included, item.reason)
        for item in allocate_candidates(candidates)
    }


def test_duplicate_fact_is_not_counted_twice():
    result = _result([
        ScoreCandidate(1, 10, "same-award", Decimal("5")),
        ScoreCandidate(2, 10, "same-award", Decimal("3")),
    ])
    assert result == {1: (True, None), 2: (False, "duplicate_fact")}


def test_max_count_selects_highest_scores_deterministically():
    candidates = [
        ScoreCandidate(3, 10, "c", Decimal("2"), max_count=2),
        ScoreCandidate(2, 10, "b", Decimal("5"), max_count=2),
        ScoreCandidate(1, 10, "a", Decimal("5"), max_count=2),
    ]
    result = _result(candidates)
    assert result == {
        1: (True, None),
        2: (True, None),
        3: (False, "max_count_exceeded"),
    }
    assert allocate_candidates(candidates) == allocate_candidates(reversed(candidates))


def test_count_limits_are_independent_per_rule_version():
    result = _result([
        ScoreCandidate(1, 10, "a", Decimal("5"), max_count=1),
        ScoreCandidate(2, 10, "b", Decimal("4"), max_count=1),
        ScoreCandidate(3, 11, "c", Decimal("3"), max_count=1),
    ])
    assert result[1] == (True, None)
    assert result[2] == (False, "max_count_exceeded")
    assert result[3] == (True, None)



def test_rule_total_cap_partially_counts_last_selected_material():
    items = [ScoreCandidate(i, 1, str(i), Decimal(score), max_count=2, total_score_cap=Decimal(8))
             for i, score in enumerate([4, 5, 6], 1)]
    allocation = allocate_candidates(items)
    assert [item.allocated_score for item in allocation] == [0, 2, 6]
    assert [item.reason for item in allocation] == ["max_count_exceeded", "rule_total_score_cap", None]
