"""Publishing immutable scoring-rule snapshots."""

import hashlib
import json

from extensions import db
from workflow_models import RuleVersion


class RulePublishingError(ValueError):
    def __init__(self, message, *, code="invalid_structured_rule", conflicts=None):
        self.code = code
        self.conflicts = conflicts or []
        super().__init__(message)


MATCH_FIELDS = (
    "competition_name", "award_level", "competition_level",
    "region", "group", "track",
)


def _conditions_overlap(left, right):
    if left == {"any": True} or right == {"any": True}:
        return True
    return left == right


def _validate_structured_snapshot(snapshot):
    terms = snapshot.get("match_terms")
    if terms is None:
        return
    if snapshot.get("match_schema_version") != "material-terms-v1":
        raise RulePublishingError("结构化规则缺少受支持的匹配版本")
    if not isinstance(terms, dict) or set(terms) != set(MATCH_FIELDS):
        raise RulePublishingError("结构化规则必须显式提供完整匹配维度")
    if not terms.get("competition_name") or not terms.get("award_level"):
        raise RulePublishingError("竞赛名称和奖项等级不能为空")


def _find_overlapping_versions(rule, snapshot):
    terms = snapshot.get("match_terms")
    if terms is None:
        return []
    query = (
        db.session.query(RuleVersion)
        .filter(RuleVersion.status == "published", RuleVersion.rule_id != rule.id)
        .with_for_update()
    )
    conflicts = []
    for version in query.all():
        other = version.snapshot
        other_terms = other.get("match_terms")
        if not isinstance(other_terms, dict):
            continue
        if other.get("cycle_code") != snapshot.get("cycle_code"):
            continue
        if other.get("sub_type") != snapshot.get("sub_type"):
            continue
        left_faculty, right_faculty = snapshot.get("faculty_id"), other.get("faculty_id")
        if left_faculty is not None and right_faculty is not None and left_faculty != right_faculty:
            continue
        if all(_conditions_overlap(terms.get(field), other_terms.get(field))
               for field in MATCH_FIELDS):
            conflicts.append(version.id)
    return sorted(conflicts)


def _number(value):
    return float(value) if value is not None else None


def rule_snapshot(rule, *, cycle_code=None):
    calculation = rule.calculation
    return {
        "name": rule.name,
        "type": rule.type,
        "sub_type": rule.sub_type,
        "research_type": rule.research_type,
        "score": _number(rule.score),
        "max_score": _number(rule.max_score),
        "max_count": rule.max_count,
        "description": rule.description,
        "faculty_id": rule.faculty_id,
        "calculation_formula": rule.calculation_formula,
        "calculation": (
            {
                "calculation_type": calculation.calculation_type,
                "formula": calculation.formula,
                "parameters": calculation.parameters,
                "max_score": _number(calculation.max_score),
                "precision": calculation.precision,
            }
            if calculation
            else None
        ),
        "cycle_code": int(cycle_code) if cycle_code is not None else None,
        "match_terms": rule.match_terms,
        "match_schema_version": rule.match_schema_version,
    }


def publish_rule_version(rule, *, published_by=None, cycle_code=None):
    """Create or idempotently reuse the immutable version of current rule content."""
    if rule.id is None:
        db.session.flush()
    if cycle_code is None:
        from use_cases.cycles import current_cycle_policy

        active_cycle = current_cycle_policy(required=False)
        cycle_code = active_cycle.cycle_code if active_cycle else None
    snapshot = rule_snapshot(rule, cycle_code=cycle_code)
    _validate_structured_snapshot(snapshot)
    digest = RuleVersion.canonical_digest(snapshot)
    existing = RuleVersion.query.filter_by(rule_id=rule.id, digest=digest).first()
    if existing is not None:
        return existing, False
    conflicts = _find_overlapping_versions(rule, snapshot)
    if conflicts:
        raise RulePublishingError(
            "结构化规则与已发布规则重叠",
            code="ambiguous_scoring_rules", conflicts=conflicts,
        )
    latest = (
        RuleVersion.query.filter_by(rule_id=rule.id)
        .order_by(RuleVersion.version.desc())
        .first()
    )
    actor_id = getattr(published_by, "id", published_by)
    version = RuleVersion(
        rule_id=rule.id,
        version=(latest.version + 1 if latest else 1),
        status="published",
        snapshot=snapshot,
        digest=digest,
        match_terms_digest=(
            hashlib.sha256(json.dumps(
                snapshot["match_terms"], ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")).hexdigest()
            if snapshot["match_terms"] is not None else None
        ),
        match_schema_version=(
            snapshot["match_schema_version"]
            if snapshot["match_terms"] is not None else None
        ),
        published_by=actor_id,
    )
    db.session.add(version)
    db.session.flush()
    return version, True
