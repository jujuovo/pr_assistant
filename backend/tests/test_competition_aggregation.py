import json
from decimal import Decimal
from pathlib import Path

import pytest

from domain.competition_scoring import (
    CompetitionAggregationCandidate,
    CompetitionScoringError,
    aggregate_competition_candidates,
    calculate_competition_candidate,
)


def package():
    path = Path(__file__).parents[1] / "rules" / "competition_2028.json"
    return json.loads(path.read_text(encoding="utf-8"))


def candidate(material_id, score, *, family=None, year=2027, work=None, event=None, order=None):
    family = family or f"family-{material_id}"
    return CompetitionAggregationCandidate(
        material_id=material_id,
        competition_id=f"competition-{material_id}",
        event_family=family,
        event_year=year,
        candidate_score=Decimal(str(score)),
        work_key=work or f"work-{material_id}",
        event_key=event or f"event-{material_id}",
        evidence_date=f"2027-01-{material_id:02d}",
        rule_order=material_id if order is None else order,
    )


def result_map(result):
    return {item.material_id: item for item in result.items}


@pytest.mark.parametrize(
    "percentile,award,base",
    [("0.2", "first_or_above", "10"), ("1.5", "second", "5"), ("3", "third", "2")],
)
def test_csp_thresholds_map_to_national_awards(percentile, award, base):
    result = calculate_competition_candidate(
        package(), competition_id="c28-ccf-csp", level="national", award=award,
        csp_percentile=percentile, participation_mode="individual",
    )
    assert result.base_score == Decimal(base).quantize(Decimal("0.0001"))


def test_csp_outside_threshold_is_not_silently_zero():
    with pytest.raises(CompetitionScoringError) as error:
        calculate_competition_candidate(
            package(), competition_id="c28-ccf-csp", level="national", award="third",
            csp_percentile="3.01", participation_mode="individual",
        )
    assert error.value.code == "csp_not_eligible"


def test_special_keep_highest_stages_and_top_three_have_stable_reasons():
    values = [
        candidate(1, 6, family="csp"), candidate(2, 5, family="csp"),
        candidate(3, 7, family="icpc", year=2027), candidate(4, 4, family="ccpc", year=2027),
        candidate(5, 8, event="shared-event"), candidate(6, 3, event="shared-event"),
        candidate(7, 9, work="shared-work"), candidate(8, 2, work="shared-work"),
        candidate(9, 10), candidate(10, 1),
    ]
    result = result_map(aggregate_competition_candidates(values))
    assert result[2].exclusion_reason == "csp_lower_score"
    assert result[4].exclusion_reason == "icpc_ccpc_same_year_lower_score"
    assert result[6].exclusion_reason == "same_event_lower_score"
    assert result[8].exclusion_reason == "same_work_lower_score"
    assert result[10].exclusion_reason == "competition_top_three_limit"
    assert {item.material_id for item in result.values() if item.included} == {5, 7, 9}


def test_order_independence_tie_break_and_recalculation_are_deterministic():
    values = [candidate(3, 5, order=2), candidate(1, 5, order=1), candidate(2, 5, order=1), candidate(4, 4)]
    first = aggregate_competition_candidates(values)
    second = aggregate_competition_candidates(reversed(values))
    third = aggregate_competition_candidates(values)
    assert first == second == third
    assert result_map(first)[4].exclusion_reason == "competition_top_three_limit"


def test_excluded_item_is_replaced_when_higher_item_disappears():
    values = [candidate(1, 4), candidate(2, 3), candidate(3, 2), candidate(4, 1)]
    initial = result_map(aggregate_competition_candidates(values))
    rebuilt = result_map(aggregate_competition_candidates(values[1:]))
    assert initial[4].included is False
    assert rebuilt[4].included is True


def test_specialty_cap_is_explained_without_destroying_raw_details():
    result = aggregate_competition_candidates(
        [candidate(1, 8), candidate(2, 6), candidate(3, 4)], specialty_other_score=2
    )
    assert result.competition_total == Decimal("18.0000")
    assert result.specialty_effective_total == Decimal("15.0000")
    assert result.cap_reason == "academic_specialty_cap"
    assert sum(item.candidate_score for item in result.items) == Decimal("18.0000")
