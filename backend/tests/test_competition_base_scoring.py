import json
from decimal import Decimal
from pathlib import Path

import pytest

from domain.competition_scoring import CompetitionScoringError, calculate_competition_candidate


@pytest.fixture(scope="module")
def package():
    path = Path(__file__).parents[1] / "rules" / "competition_2028.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "competition_id,level,award,expected_base",
    [
        ("c01-china-college-student-innovation", "national", "first_or_above", "30"),
        ("c01-china-college-student-innovation", "national", "second", "15"),
        ("c01-china-college-student-innovation", "national", "third", "10"),
        ("c07-national-software-innovation", "national", "first_or_above", "15"),
        ("c07-national-software-innovation", "national", "second", "10"),
        ("c07-national-software-innovation", "national", "third", "5"),
        ("c09-computer-design", "national", "first_or_above", "10"),
        ("c09-computer-design", "national", "second", "5"),
        ("c09-computer-design", "national", "third", "2"),
        ("c24-cybersecurity-elite", "provincial", "first_or_above", "1"),
        ("c24-cybersecurity-elite", "provincial", "second", "0.5"),
    ],
)
def test_formal_matrix_combinations(package, competition_id, level, award, expected_base):
    result = calculate_competition_candidate(
        package, competition_id=competition_id, level=level, award=award,
        participation_mode="individual",
    )
    assert result.base_score == Decimal(expected_base).quantize(Decimal("0.0001"))
    assert result.candidate_score == (Decimal(expected_base) / 3).quantize(Decimal("0.0001"))


def test_provincial_third_award_is_rejected(package):
    with pytest.raises(CompetitionScoringError) as error:
        calculate_competition_candidate(
            package, competition_id="c24-cybersecurity-elite", level="provincial",
            award="third", participation_mode="individual",
        )
    assert error.value.code == "provincial_third_award_forbidden"


@pytest.mark.parametrize(
    "competition_id,event_format,expected_base",
    [
        ("c04-icpc", "regional", "15"),
        ("c04-icpc", "world_final", "30"),
        ("c05-ccpc", "national", "15"),
    ],
)
def test_icpc_ccpc_policy_category_overrides_combined_catalog_row(
    package, competition_id, event_format, expected_base
):
    result = calculate_competition_candidate(
        package, competition_id=competition_id, level="national",
        award="first_or_above", event_format=event_format,
        participation_mode="individual",
    )
    assert result.base_score == Decimal(expected_base).quantize(Decimal("0.0001"))


def test_icpc_invitation_is_rejected(package):
    with pytest.raises(CompetitionScoringError) as error:
        calculate_competition_candidate(
            package, competition_id="c04-icpc", level="national",
            award="first_or_above", event_format="invitation",
            participation_mode="individual",
        )
    assert error.value.code == "invitation_ineligible"


@pytest.mark.parametrize(
    "competition_id,size,rank,coefficient,policy",
    [
        ("c01-china-college-student-innovation", 5, 1, "0.3333", "special_team_leader"),
        ("c01-china-college-student-innovation", 5, 3, "0.2500", "special_team_rank_2_3"),
        ("c01-china-college-student-innovation", 5, 5, "0.2000", "special_team_rank_4_5"),
        ("c09-computer-design", 2, 2, "0.3333", "generic_team_size_2"),
        ("c09-computer-design", 4, 4, "0.2500", "generic_team_size_3_5"),
        ("c09-computer-design", 8, 5, "0.2000", "generic_team_first_five"),
    ],
)
def test_team_allocation_coefficients(package, competition_id, size, rank, coefficient, policy):
    result = calculate_competition_candidate(
        package, competition_id=competition_id, level="national", award="first_or_above",
        participation_mode="team", team_size=size, personal_rank=rank,
    )
    assert result.coefficient == Decimal(coefficient)
    assert result.allocation_policy == policy


@pytest.mark.parametrize("size,rank,code", [(0, 1, "invalid_team_size"), (3, 0, "invalid_team_rank"), (3, 4, "invalid_team_rank"), (8, 6, "team_rank_not_eligible")])
def test_illegal_team_rank_is_rejected(package, size, rank, code):
    with pytest.raises(CompetitionScoringError) as error:
        calculate_competition_candidate(
            package, competition_id="c09-computer-design", level="national",
            award="first_or_above", participation_mode="team",
            team_size=size, personal_rank=rank,
        )
    assert error.value.code == code
