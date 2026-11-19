"""Draft and published ranking policies."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class RankingCandidate:
    student_id: str
    score: Decimal | None
    snapshot_id: int | None
    eligible: bool
    exclusion_reason: str | None = None


@dataclass(frozen=True)
class RankingPlacement:
    student_id: str
    score: Decimal | None
    snapshot_id: int | None
    eligible: bool
    rank: int | None
    display_order: int
    exclusion_reason: str | None


def candidate(student_id, academic_score, snapshot_id, comprehensive_score):
    if academic_score is None:
        return RankingCandidate(student_id, None, snapshot_id, False, "missing_academic_score")
    if snapshot_id is None or comprehensive_score is None:
        return RankingCandidate(student_id, None, None, False, "missing_score_snapshot")
    return RankingCandidate(
        student_id,
        Decimal(str(comprehensive_score)),
        snapshot_id,
        True,
        None,
    )


def competition_ranking(candidates, precision=4):
    if not isinstance(precision, int) or not 0 <= precision <= 8:
        raise ValueError("ranking precision must be between 0 and 8")
    quantum = Decimal(1).scaleb(-precision)
    eligible = sorted(
        (item for item in candidates if item.eligible),
        key=lambda item: (
            -item.score.quantize(quantum, rounding=ROUND_HALF_UP),
            item.student_id,
        ),
    )
    excluded = sorted((item for item in candidates if not item.eligible), key=lambda item: item.student_id)
    placements = []
    previous_score = None
    previous_rank = None
    for index, item in enumerate(eligible, start=1):
        rounded = item.score.quantize(quantum, rounding=ROUND_HALF_UP)
        rank = previous_rank if previous_score == rounded else index
        placements.append(
            RankingPlacement(
                item.student_id, rounded, item.snapshot_id, True, rank, index, None
            )
        )
        previous_score, previous_rank = rounded, rank
    for item in excluded:
        placements.append(
            RankingPlacement(
                item.student_id,
                None,
                item.snapshot_id,
                False,
                None,
                len(placements) + 1,
                item.exclusion_reason,
            )
        )
    return tuple(placements)

