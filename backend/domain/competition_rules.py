"""Validation for immutable academic-competition rule packages."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
import unicodedata
import hashlib
import json

from domain.competition_scoring import CompetitionScoringError, calculate_competition_candidate


class CompetitionPackageError(ValueError):
    def __init__(self, message, *, code="invalid_competition_package", details=None):
        super().__init__(message)
        self.code = code
        self.details = tuple(details or ())


@dataclass(frozen=True)
class ValidatedCompetitionPackage:
    package_id: str
    cycle_code: int
    catalog_count: int


COMPETITION_FACT_FIELDS = {
    "competition_id", "project_name", "award_date", "level", "award",
    "event_year", "participation_mode", "team_size", "personal_rank",
    "event_format", "csp_percentile", "group", "track", "evidence",
}
LEGACY_AUTHORITY_FIELDS = {
    "rule_id", "self_score", "final_score", "dynamic_coefficients",
    "override_score", "override_reason",
}


def _normalized_text(value, field, *, required=False, maximum=200):
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise CompetitionPackageError(f"{field} must be text", code=f"invalid_{field}")
    value = unicodedata.normalize("NFKC", value).strip()
    value = re.sub(r"\s+", " ", value)
    if required and not value:
        raise CompetitionPackageError(f"{field} is required", code=f"{field}_required")
    if len(value) > maximum:
        raise CompetitionPackageError(f"{field} is too long", code=f"invalid_{field}")
    return value or None


def normalize_competition_facts(snapshot, facts):
    if not isinstance(facts, dict):
        raise CompetitionPackageError("competition facts must be an object", code="invalid_competition_facts")
    forbidden = sorted(set(facts) & LEGACY_AUTHORITY_FIELDS)
    if forbidden:
        raise CompetitionPackageError(
            f"legacy authority fields are forbidden: {', '.join(forbidden)}",
            code="legacy_authority_field_forbidden",
        )
    unknown = sorted(set(facts) - COMPETITION_FACT_FIELDS)
    if unknown:
        raise CompetitionPackageError(
            f"unknown competition fields: {', '.join(unknown)}",
            code="unknown_competition_field",
        )
    required = set(snapshot["field_schema"]["required"])
    missing = sorted(field for field in required if facts.get(field) in (None, ""))
    if missing:
        raise CompetitionPackageError(
            f"missing competition fields: {', '.join(missing)}",
            code="competition_fields_missing",
            details=missing,
        )
    catalog = {item["competition_id"]: item for item in snapshot["catalog"]}
    competition_id = facts.get("competition_id")
    item = catalog.get(competition_id)
    if item is None:
        raise CompetitionPackageError("competition is outside the formal catalog", code="unknown_competition")
    try:
        award_date = date.fromisoformat(str(facts["award_date"]))
    except (TypeError, ValueError) as error:
        raise CompetitionPackageError("award_date must be an ISO date", code="invalid_award_date") from error
    period = snapshot["evidence_period"]
    if not date.fromisoformat(period["start"]) <= award_date <= date.fromisoformat(period["end"]):
        raise CompetitionPackageError("award_date is outside the 2028 evidence period", code="award_date_ineligible")
    event_year = facts.get("event_year")
    if isinstance(event_year, bool) or not isinstance(event_year, int) or not 2025 <= event_year <= 2028:
        raise CompetitionPackageError("event_year is invalid", code="invalid_event_year")
    participation_mode = facts.get("participation_mode")
    if participation_mode not in snapshot["field_schema"]["participation_modes"]:
        raise CompetitionPackageError("participation_mode is invalid", code="invalid_participation_mode")
    normalized = {
        "competition_id": competition_id,
        "competition_name": item["name"],
        "category": item["category"],
        "project_name": _normalized_text(facts.get("project_name"), "project_name", required=True),
        "award_date": award_date.isoformat(),
        "level": facts.get("level"),
        "award": facts.get("award"),
        "event_year": event_year,
        "participation_mode": participation_mode,
    }
    for field in ("event_format", "group", "track"):
        if facts.get(field) is not None:
            normalized[field] = _normalized_text(facts[field], field)
    if participation_mode == "team":
        for field in snapshot["field_schema"]["team_required"]:
            if facts.get(field) is None:
                raise CompetitionPackageError(
                    f"{field} is required for team results", code="team_fields_missing"
                )
        normalized["team_size"] = facts["team_size"]
        normalized["personal_rank"] = facts["personal_rank"]
    if item["event_family"] == "csp":
        if facts.get("csp_percentile") is None:
            raise CompetitionPackageError("csp_percentile is required", code="csp_percentile_required")
        normalized["csp_percentile"] = str(facts["csp_percentile"])
    try:
        candidate = calculate_competition_candidate(
            snapshot,
            competition_id=competition_id,
            level=normalized["level"], award=normalized["award"],
            participation_mode=participation_mode,
            team_size=normalized.get("team_size"), personal_rank=normalized.get("personal_rank"),
            event_format=normalized.get("event_format"),
            csp_percentile=normalized.get("csp_percentile"),
        )
    except CompetitionScoringError as error:
        raise CompetitionPackageError(str(error), code=error.code) from error
    if "evidence" in facts:
        from domain.ocr_evidence import normalize_evidence
        try:
            normalized["evidence"] = normalize_evidence(facts["evidence"])
        except ValueError as error:
            raise CompetitionPackageError(str(error), code="invalid_certificate_evidence") from error
    normalized["candidate_score"] = str(candidate.candidate_score)
    normalized["allocation_policy"] = candidate.allocation_policy
    normalized["project_name_key"] = re.sub(r"\s+", "", normalized["project_name"]).casefold()
    return normalized


def competition_identity_keys(snapshot, normalized):
    item = next(
        value for value in snapshot["catalog"]
        if value["competition_id"] == normalized["competition_id"]
    )
    identity_fields = (
        "competition_id", "project_name_key", "award_date", "level", "award",
        "event_year", "participation_mode", "team_size", "personal_rank",
        "event_format", "csp_percentile", "group", "track",
    )
    payload = {field: normalized.get(field) for field in identity_fields}
    duplicate_digest = hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    work_key = hashlib.sha256(normalized["project_name_key"].encode("utf-8")).hexdigest()
    event_payload = {
        "event_family": item["event_family"],
        "event_year": normalized["event_year"],
    }
    event_key = hashlib.sha256(json.dumps(
        event_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return duplicate_digest, work_key, event_key


def _positive_decimal(value, path, errors):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError):
        errors.append(f"{path} must be numeric")
        return
    if not parsed.is_finite() or parsed <= 0:
        errors.append(f"{path} must be positive")


def validate_competition_package(snapshot):
    if not isinstance(snapshot, dict):
        raise CompetitionPackageError("package must be an object")
    errors = []
    required_top = {
        "package_id", "cycle_code", "evidence_period", "score_matrix",
        "policy", "catalog", "field_schema",
    }
    missing = sorted(required_top - set(snapshot))
    if missing:
        errors.append(f"missing top-level fields: {', '.join(missing)}")

    policy = snapshot.get("policy")
    limit = policy.get("competition_max_count") if isinstance(policy, dict) else None
    if type(limit) is not int or limit < 0:
        errors.append("competition_max_count must be a nonnegative integer")
    cycle_code = snapshot.get("cycle_code")
    if not isinstance(cycle_code, int) or not 2000 <= cycle_code <= 2100:
        errors.append("cycle_code must be between 2000 and 2100")
    period = snapshot.get("evidence_period") or {}
    if cycle_code == 2028 and period != {
        "start": "2025-09-01", "end": "2028-08-31", "boundary": "inclusive"
    }:
        errors.append("2028 evidence period must be inclusive 2025-09-01..2028-08-31")
    else:
        try:
            start = date.fromisoformat(period["start"])
            end = date.fromisoformat(period["end"])
            if period.get("boundary") != "inclusive" or start > end:
                errors.append("evidence period must be ordered and inclusive")
            if isinstance(cycle_code, int) and end.year != cycle_code:
                errors.append("evidence period end year must match cycle_code")
        except (KeyError, TypeError, ValueError):
            errors.append("evidence period dates must be ISO dates")

    matrix = snapshot.get("score_matrix") or {}
    expected_awards = {
        "national": {"first_or_above", "second", "third"},
        "provincial": {"first_or_above", "second"},
    }
    for level, awards in expected_awards.items():
        actual = matrix.get(level)
        if not isinstance(actual, dict) or set(actual) != awards:
            errors.append(f"score_matrix.{level} must contain exactly {sorted(awards)}")
            continue
        for award, scores in actual.items():
            if not isinstance(scores, dict) or set(scores) != {"A+", "A", "A-"}:
                errors.append(f"score_matrix.{level}.{award} must cover A+/A/A-")
                continue
            for category, score in scores.items():
                _positive_decimal(score, f"score_matrix.{level}.{award}.{category}", errors)

    schema = snapshot.get("field_schema") or {}
    required_facts = {
        "competition_id", "project_name", "award_date", "level", "award",
        "event_year", "participation_mode",
    }
    if not required_facts <= set(schema.get("required") or []):
        errors.append("field_schema.required is incomplete")
    if set((schema.get("awards") or {}).get("provincial") or []) != {
        "first_or_above", "second"
    }:
        errors.append("provincial awards must exclude third")
    if set(schema.get("team_required") or []) != {"team_size", "personal_rank"}:
        errors.append("team field schema must require size and personal rank")

    catalog = snapshot.get("catalog") or []
    if not isinstance(catalog, list) or not catalog:
        errors.append("catalog must be a non-empty list")
        catalog = []
    ids, names = set(), set()
    for index, item in enumerate(catalog):
        path = f"catalog[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{path} must be an object")
            continue
        competition_id = item.get("competition_id")
        name = item.get("name")
        if not competition_id or competition_id in ids:
            errors.append(f"{path}.competition_id is missing or duplicated")
        ids.add(competition_id)
        if not name or name in names:
            errors.append(f"{path}.name is missing or duplicated")
        names.add(name)
        if item.get("category") not in {"A+", "A", "A-"}:
            errors.append(f"{path}.category is invalid")
        levels = item.get("levels")
        if not levels or not set(levels) <= {"national", "provincial"}:
            errors.append(f"{path}.levels is invalid")
        if not isinstance(item.get("source_row"), int):
            errors.append(f"{path}.source_row is required")

    policy = snapshot.get("policy") or {}
    special_ids = set(policy.get("special_ranked_competition_ids") or [])
    missing_refs = sorted(special_ids - ids)
    if missing_refs:
        errors.append(f"unknown special competition references: {', '.join(missing_refs)}")
    thresholds = ((policy.get("csp") or {}).get("thresholds") or [])
    limits = [Decimal(str(item.get("max_percent"))) for item in thresholds if isinstance(item, dict)]
    if limits != sorted(set(limits)) or len(limits) != 3:
        errors.append("CSP thresholds must contain three unique ascending boundaries")
    if (policy.get("icpc_ccpc") or {}).get("invitation_eligible") is not False:
        errors.append("ICPC/CCPC invitation results must be ineligible")

    if errors:
        raise CompetitionPackageError(
            "competition package validation failed", details=errors
        )
    return ValidatedCompetitionPackage(
        package_id=snapshot["package_id"],
        cycle_code=snapshot["cycle_code"],
        catalog_count=len(catalog),
    )
