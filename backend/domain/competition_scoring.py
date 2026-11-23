"""Pure policies for formal academic-competition scoring."""

from domain.competition_levels import competition_award_levels

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


FOUR_PLACES = Decimal("0.0001")


class CompetitionScoringError(ValueError):
    def __init__(self, message, *, code="invalid_competition_fact"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CompetitionCandidateScore:
    base_score: Decimal
    coefficient: Decimal
    candidate_score: Decimal
    allocation_policy: str


def csp_award_for_percentile(package, percentile):
    try:
        value = Decimal(str(percentile))
    except Exception as error:
        raise CompetitionScoringError("CSP percentile must be numeric", code="invalid_csp_percentile") from error
    if not value.is_finite() or value < 0:
        raise CompetitionScoringError("CSP percentile must be non-negative", code="invalid_csp_percentile")
    for threshold in package["policy"]["csp"]["thresholds"]:
        if value <= Decimal(str(threshold["max_percent"])):
            return threshold["award"]
    raise CompetitionScoringError("CSP result is outside the top 3%", code="csp_not_eligible")


def _decimal(value):
    return Decimal(str(value)).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def _team_coefficient(package, competition_id, participation_mode, team_size, personal_rank):
    policy = package["policy"]
    if participation_mode == "individual":
        return Decimal(1) / Decimal(3), "individual_one_third"
    if participation_mode != "team":
        raise CompetitionScoringError("participation_mode must be individual or team")
    if isinstance(team_size, bool) or not isinstance(team_size, int) or team_size < 1:
        raise CompetitionScoringError("team_size must be a positive integer", code="invalid_team_size")
    if isinstance(personal_rank, bool) or not isinstance(personal_rank, int):
        raise CompetitionScoringError("personal_rank must be an integer", code="invalid_team_rank")
    if personal_rank < 1 or personal_rank > team_size:
        raise CompetitionScoringError("personal_rank is outside the team", code="invalid_team_rank")

    if competition_id in policy["special_ranked_competition_ids"]:
        if personal_rank == 1:
            return Decimal(1) / Decimal(3), "special_team_leader"
        if personal_rank <= 3:
            return Decimal(1) / Decimal(4), "special_team_rank_2_3"
        if personal_rank <= 5:
            return Decimal(1) / Decimal(5), "special_team_rank_4_5"
        raise CompetitionScoringError(
            "only the first five ranked members are eligible",
            code="team_rank_not_eligible",
        )
    if team_size == 1:
        raise CompetitionScoringError(
            "a one-person result must use individual mode", code="invalid_team_size"
        )
    if team_size == 2:
        return Decimal(1) / Decimal(3), "generic_team_size_2"
    if team_size <= 5:
        return Decimal(1) / Decimal(team_size), "generic_team_size_3_5"
    if personal_rank > 5:
        raise CompetitionScoringError(
            "only the first five core members are eligible",
            code="team_rank_not_eligible",
        )
    return Decimal(1) / Decimal(5), "generic_team_first_five"


def calculate_competition_candidate(
    package, *, competition_id, level, award, participation_mode,
    team_size=None, personal_rank=None, event_format=None, csp_percentile=None,
):
    catalog = {item["competition_id"]: item for item in package["catalog"]}
    item = catalog.get(competition_id)
    if item is None:
        raise CompetitionScoringError(
            "competition is outside the formal catalog", code="unknown_competition"
        )
    if level not in competition_award_levels(item):
        raise CompetitionScoringError(
            "level is not allowed for this competition", code="invalid_competition_level"
        )
    if item["event_family"] == "csp":
        award = csp_award_for_percentile(package, csp_percentile)
        level = "national"
    level_matrix = package["score_matrix"].get(level) or {}
    award_matrix = level_matrix.get(award)
    if award_matrix is None:
        code = "provincial_third_award_forbidden" if level == "provincial" and award == "third" else "invalid_award"
        raise CompetitionScoringError("award is not scoreable at this level", code=code)
    category = item["category"]
    if item["event_family"] == "icpc":
        if event_format == "invitation":
            raise CompetitionScoringError("ICPC invitation results are ineligible", code="invitation_ineligible")
        if event_format not in item["formats"]:
            raise CompetitionScoringError("ICPC format is required", code="invalid_event_format")
        category = "A+" if event_format == "world_final" else "A"
    elif item["event_family"] == "ccpc":
        if event_format == "invitation":
            raise CompetitionScoringError("CCPC invitation results are ineligible", code="invitation_ineligible")
        if event_format not in (None, "national"):
            raise CompetitionScoringError("CCPC format is invalid", code="invalid_event_format")
        category = "A"
    if category not in award_matrix:
        raise CompetitionScoringError("category matrix is incomplete", code="incomplete_score_matrix")
    base = Decimal(str(award_matrix[category]))
    coefficient, allocation_policy = _team_coefficient(
        package, competition_id, participation_mode, team_size, personal_rank
    )
    return CompetitionCandidateScore(
        base_score=_decimal(base),
        coefficient=_decimal(coefficient),
        candidate_score=_decimal(base * coefficient),
        allocation_policy=allocation_policy,
    )


@dataclass(frozen=True)
class CompetitionAggregationCandidate:
    material_id: int
    competition_id: str
    event_family: str
    event_year: int
    candidate_score: Decimal
    work_key: str
    event_key: str
    evidence_date: str
    rule_order: int


@dataclass(frozen=True)
class CompetitionAggregationItem:
    material_id: int
    candidate_score: Decimal
    effective_score: Decimal
    included: bool
    exclusion_reason: str | None


@dataclass(frozen=True)
class CompetitionAggregationResult:
    items: tuple[CompetitionAggregationItem, ...]
    competition_total: Decimal
    specialty_effective_total: Decimal
    cap_reason: str | None


def aggregate_competition_candidates(candidates, *, max_count=3, specialty_other_score=0, specialty_cap=15):
    """Apply every formal keep-highest stage in deterministic policy order."""
    candidates = tuple(candidates)
    by_id = {item.material_id: item for item in candidates}
    if len(by_id) != len(candidates):
        raise CompetitionScoringError("material ids must be unique", code="duplicate_material_id")
    reasons = {}

    def order_key(item):
        return (-_decimal(item.candidate_score), item.rule_order, item.evidence_date, item.material_id)

    def keep_highest(groups, reason):
        for members in groups.values():
            eligible = [item for item in members if item.material_id not in reasons]
            for item in sorted(eligible, key=order_key)[1:]:
                reasons[item.material_id] = reason

    csp_groups = {}
    for item in candidates:
        if item.event_family == "csp":
            csp_groups.setdefault("csp", []).append(item)
    keep_highest(csp_groups, "csp_lower_score")

    icpc_groups = {}
    for item in candidates:
        if item.event_family in {"icpc", "ccpc"}:
            icpc_groups.setdefault(item.event_year, []).append(item)
    keep_highest(icpc_groups, "icpc_ccpc_same_year_lower_score")

    event_groups = {}
    for item in candidates:
        event_groups.setdefault(item.event_key, []).append(item)
    keep_highest(event_groups, "same_event_lower_score")

    work_groups = {}
    for item in candidates:
        work_groups.setdefault(item.work_key, []).append(item)
    keep_highest(work_groups, "same_work_lower_score")

    remaining = sorted(
        (item for item in candidates if item.material_id not in reasons),
        key=order_key,
    )
    if type(max_count) is not int or max_count < 0:
        raise CompetitionScoringError("competition_max_count must be a nonnegative integer", code="invalid_count_limit")
    for item in remaining[max_count:]:
        reasons[item.material_id] = "competition_top_three_limit" if max_count == 3 else "competition_count_limit"

    items = tuple(
        CompetitionAggregationItem(
            material_id=item.material_id,
            candidate_score=_decimal(item.candidate_score),
            effective_score=(Decimal("0.0000") if item.material_id in reasons else _decimal(item.candidate_score)),
            included=item.material_id not in reasons,
            exclusion_reason=reasons.get(item.material_id),
        )
        for item in sorted(candidates, key=lambda value: value.material_id)
    )
    total = sum((item.effective_score for item in items), Decimal("0.0000"))
    cap = _decimal(specialty_cap)
    combined = total + _decimal(specialty_other_score)
    specialty_total = min(combined, cap)
    return CompetitionAggregationResult(
        items=items,
        competition_total=_decimal(total),
        specialty_effective_total=_decimal(specialty_total),
        cap_reason="academic_specialty_cap" if combined > cap else None,
    )
