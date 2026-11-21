"""Auditable score calculation policies."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json


FOUR_PLACES = Decimal("0.0001")


def decimal(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ScoreFact:
    entry_id: int
    score_group: str
    effective_score: Decimal
    rule_version_id: int
    included: bool = True
    status: str = "active"


@dataclass(frozen=True)
class ScoreProjection:
    academic_base_score: Decimal
    academic_weight: Decimal
    specialty_raw_score: Decimal
    specialty_score: Decimal
    performance_raw_score: Decimal
    performance_score: Decimal
    comprehensive_score: Decimal
    input_digest: str
    rule_version_ids: tuple[int, ...]
    breakdown: tuple[dict, ...]


class ScoreRuleError(ValueError):
    def __init__(self, message, *, code="invalid_rule"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ScoreCalculation:
    raw_score: Decimal
    adjusted_score: Decimal
    effective_score: Decimal
    coefficient: Decimal
    capped: bool


@dataclass(frozen=True)
class ScoreCandidate:
    entry_id: int
    rule_version_id: int
    semantic_key: str
    effective_score: Decimal
    max_count: int | None = None
    total_score_cap: Decimal | None = None


@dataclass(frozen=True)
class ScoreAllocation:
    entry_id: int
    included: bool
    reason: str | None
    allocated_score: Decimal = Decimal(0)


def allocate_candidates(candidates) -> tuple[ScoreAllocation, ...]:
    """Deterministically deduplicate and apply each rule's count limit."""
    ordered = sorted(
        candidates,
        key=lambda item: (
            item.rule_version_id,
            -decimal(item.effective_score),
            item.entry_id,
        ),
    )
    seen_semantics = set()
    included_by_rule = {}
    totals = {}
    result = []
    for item in ordered:
        semantic_identity = (item.rule_version_id, item.semantic_key)
        if semantic_identity in seen_semantics:
            result.append(ScoreAllocation(item.entry_id, False, "duplicate_fact"))
            continue
        seen_semantics.add(semantic_identity)
        used = included_by_rule.get(item.rule_version_id, 0)
        if item.max_count is not None and used >= item.max_count:
            result.append(ScoreAllocation(item.entry_id, False, "max_count_exceeded"))
            continue
        included_by_rule[item.rule_version_id] = used + 1
        allocated = decimal(item.effective_score)
        if item.total_score_cap is not None:
            used_score = totals.get(item.rule_version_id, Decimal(0))
            allocated = min(allocated, max(Decimal(0), decimal(item.total_score_cap) - used_score))
            totals[item.rule_version_id] = used_score + allocated
        limited = allocated < item.effective_score
        result.append(ScoreAllocation(item.entry_id, bool(allocated) or not limited,
                                      "rule_total_score_cap" if limited else None, allocated))
    return tuple(sorted(result, key=lambda item: item.entry_id))


def _rule_number(value, label, *, required=True) -> Decimal | None:
    if value is None and not required:
        return None
    if isinstance(value, bool):
        raise ScoreRuleError(f"{label} must be a finite non-negative number")
    try:
        result = Decimal(str(value))
    except Exception as error:
        raise ScoreRuleError(f"{label} must be a finite non-negative number") from error
    if not result.is_finite() or result < 0:
        raise ScoreRuleError(f"{label} must be a finite non-negative number")
    return result


def calculate_score(rule_snapshot, *, coefficient=1) -> ScoreCalculation:
    """Calculate one score fact from an immutable, already-selected rule."""
    if not isinstance(rule_snapshot, dict):
        raise ScoreRuleError("no applicable published rule", code="no_applicable_rule")
    raw = _rule_number(rule_snapshot.get("score"), "score")
    factor = _rule_number(coefficient, "coefficient")
    maximum = _rule_number(rule_snapshot.get("max_score"), "max_score", required=False)
    adjusted = raw * factor
    effective = min(adjusted, maximum) if maximum is not None else adjusted
    return ScoreCalculation(
        raw_score=raw.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP),
        adjusted_score=adjusted.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP),
        effective_score=effective.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP),
        coefficient=factor.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP),
        capped=maximum is not None and adjusted > maximum,
    )


def build_score_projection(
    academic_base_score,
    facts,
    *,
    academic_weight=Decimal("80"),
    specialty_max=None,
    performance_max=None,
) -> ScoreProjection:
    """Build a deterministic projection from already-adjudicated score facts."""
    active = sorted(
        (
            fact
            for fact in facts
            if fact.status == "active" and fact.included
        ),
        key=lambda item: item.entry_id,
    )
    specialty_raw = sum(
        (decimal(item.effective_score) for item in active if item.score_group == "academic"),
        Decimal("0"),
    )
    performance_raw = sum(
        (
            decimal(item.effective_score)
            for item in active
            if item.score_group == "comprehensive"
        ),
        Decimal("0"),
    )
    academic = decimal(academic_base_score)
    weight = decimal(academic_weight)
    specialty_cap = (
        _rule_number(specialty_max, "specialty_max", required=False)
        if specialty_max is not None else None
    )
    performance_cap = (
        _rule_number(performance_max, "performance_max", required=False)
        if performance_max is not None else None
    )
    specialty = min(specialty_raw, specialty_cap) if specialty_cap is not None else specialty_raw
    performance = min(performance_raw, performance_cap) if performance_cap is not None else performance_raw
    total = (academic * weight / Decimal("100") + specialty + performance).quantize(
        FOUR_PLACES, rounding=ROUND_HALF_UP
    )
    breakdown = tuple(
        {
            "entry_id": item.entry_id,
            "score_group": item.score_group,
            "effective_score": str(decimal(item.effective_score)),
            "rule_version_id": item.rule_version_id,
        }
        for item in active
    )
    digest_payload = {
        "academic_base_score": str(academic),
        "academic_weight": str(weight),
        "specialty_max": str(specialty_cap) if specialty_cap is not None else None,
        "performance_max": str(performance_cap) if performance_cap is not None else None,
        "entries": breakdown,
    }
    digest = hashlib.sha256(
        json.dumps(
            digest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    return ScoreProjection(
        academic_base_score=academic,
        academic_weight=weight,
        specialty_raw_score=decimal(specialty_raw),
        specialty_score=decimal(specialty),
        performance_raw_score=decimal(performance_raw),
        performance_score=decimal(performance),
        comprehensive_score=total,
        input_digest=digest,
        rule_version_ids=tuple(sorted({item.rule_version_id for item in active})),
        breakdown=breakdown,
    )

