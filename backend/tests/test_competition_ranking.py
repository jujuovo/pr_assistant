from decimal import Decimal

import pytest

from domain.ranking import RankingCandidate, competition_ranking


def _candidate(student_id, score):
    return RankingCandidate(student_id, Decimal(score), int(student_id[1:]), True)


def test_competition_ranking_uses_113_and_stable_tie_order():
    placements = competition_ranking([
        _candidate("S2", "90"),
        _candidate("S1", "90"),
        _candidate("S3", "80"),
        _candidate("S5", "70"),
        _candidate("S4", "70"),
    ])
    assert [(item.student_id, item.rank) for item in placements] == [
        ("S1", 1), ("S2", 1), ("S3", 3), ("S4", 4), ("S5", 4)
    ]


def test_precision_controls_ties_and_repeat_is_stable():
    candidates = [_candidate("S2", "80.00004"), _candidate("S1", "80.00003")]
    first = competition_ranking(candidates, precision=4)
    second = competition_ranking(reversed(candidates), precision=4)
    assert first == second
    assert [item.rank for item in first] == [1, 1]
    more_precise = competition_ranking(candidates, precision=5)
    assert [(item.student_id, item.rank) for item in more_precise] == [("S2", 1), ("S1", 2)]


def test_excluded_students_have_no_rank_and_follow_eligible_students():
    excluded = RankingCandidate("S0", None, None, False, "missing_score_snapshot")
    placements = competition_ranking([excluded, _candidate("S1", "60")])
    assert placements[0].rank == 1
    assert placements[1].rank is None and placements[1].exclusion_reason


@pytest.mark.parametrize("precision", [-1, 9, 1.5])
def test_invalid_precision_is_rejected(precision):
    with pytest.raises(ValueError):
        competition_ranking([_candidate("S1", "60")], precision=precision)

