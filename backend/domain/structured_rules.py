"""Pure deterministic matching for immutable structured scoring rules."""
from dataclasses import dataclass


MATCH_FIELDS = (
    "competition_name", "award_level", "competition_level",
    "region", "group", "track",
)


@dataclass(frozen=True)
class RuleCandidate:
    version_id: int
    cycle_code: int
    faculty_id: int | None
    material_category: str
    terms: dict
    score: object = None


def _match_value(expected, actual):
    if isinstance(expected, dict) and expected == {"any": True}:
        return True, "explicit_any"
    if expected is None:
        return actual is None, "not_applicable" if actual is None else "expected_not_applicable"
    return expected == actual, "exact" if expected == actual else "different"


def evaluate_candidate(candidate, *, cycle_code, faculty_id, material_category, terms):
    dimensions = {
        "cycle_code": candidate.cycle_code == cycle_code,
        "faculty_id": candidate.faculty_id in (None, faculty_id),
        "material_category": candidate.material_category == material_category,
    }
    explanation = {
        key: {"expected": value, "actual": {
            "cycle_code": cycle_code, "faculty_id": faculty_id,
            "material_category": material_category,
        }[key], "matched": dimensions[key]}
        for key, value in {
            "cycle_code": candidate.cycle_code,
            "faculty_id": candidate.faculty_id,
            "material_category": candidate.material_category,
        }.items()
    }
    for field in MATCH_FIELDS:
        expected = candidate.terms.get(field)
        actual = terms.get(field)
        matched, mode = _match_value(expected, actual)
        dimensions[field] = matched
        explanation[field] = {
            "expected": expected, "actual": actual,
            "matched": matched, "mode": mode,
        }
    return all(dimensions.values()), explanation


def match_structured_rules(candidates, *, cycle_code, faculty_id,
                           material_category, terms):
    if not isinstance(terms, dict):
        raise ValueError("normalized terms are required")
    evaluated = []
    for candidate in candidates:
        matched, explanation = evaluate_candidate(
            candidate, cycle_code=cycle_code, faculty_id=faculty_id,
            material_category=material_category, terms=terms,
        )
        evaluated.append({
            "version_id": candidate.version_id,
            "matched": matched,
            "dimensions": explanation,
            "score": candidate.score,
        })
    matches = [item for item in evaluated if item["matched"]]
    if not matches:
        return {
            "status": "unmapped", "reason": "material_terms_unmapped",
            "matches": [], "evaluated": evaluated,
        }
    if len(matches) > 1:
        return {
            "status": "ambiguous", "reason": "ambiguous_scoring_rules",
            "matches": matches, "evaluated": evaluated,
            "rule_version_ids": sorted(item["version_id"] for item in matches),
        }
    return {
        "status": "matched", "reason": None,
        "match": matches[0], "matches": matches, "evaluated": evaluated,
    }
