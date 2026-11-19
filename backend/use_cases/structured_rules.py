"""Administrator use cases for structured scoring-rule drafts and publishing."""
import json
from decimal import Decimal, InvalidOperation

from extensions import db
from models import Rule
from material_models import MaterialRecord
from domain.material_terms import NORMALIZATION_VERSION, normalize_term
from use_cases.rule_versions import (
    MATCH_FIELDS, RulePublishingError, _find_overlapping_versions,
    _validate_structured_snapshot, publish_rule_version, rule_snapshot,
)


class StructuredRuleError(ValueError):
    def __init__(self, message, *, code="invalid_structured_rule", status_code=400,
                 details=None):
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def _authorize_admin(user, faculty_id=None):
    if not user or user.role != "admin" or not user.faculty_id:
        raise StructuredRuleError("只有学院管理员可管理计分规则", code="forbidden", status_code=403)
    if faculty_id not in (None, user.faculty_id):
        raise StructuredRuleError("不能管理其他学院规则", code="forbidden", status_code=403)
    return user.faculty_id


def _score(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise StructuredRuleError("分值必须为有限非负数", code="invalid_score") from None
    if not result.is_finite() or result < 0:
        raise StructuredRuleError("分值必须为有限非负数", code="invalid_score")
    return float(result)


def _terms(payload):
    source = payload.get("match_terms")
    if not isinstance(source, dict) or set(source) != set(MATCH_FIELDS):
        raise StructuredRuleError("必须提供完整结构化匹配维度", code="incomplete_match_terms")
    normalized = {}
    for field in MATCH_FIELDS:
        value = source[field]
        if value == {"any": True}:
            normalized[field] = value
        else:
            normalized[field] = normalize_term(field, value)
    if not normalized["competition_name"] or not normalized["award_level"]:
        raise StructuredRuleError("竞赛名称和奖项等级不能为空", code="incomplete_match_terms")
    return normalized


def serialize_rule(rule):
    return {
        "id": rule.id, "name": rule.name, "faculty_id": rule.faculty_id,
        "material_category": rule.sub_type, "score": rule.score,
        "max_score": rule.max_score, "max_count": rule.max_count,
        "status": rule.status, "draft_version": rule.draft_version,
        "match_terms": rule.match_terms,
        "match_schema_version": rule.match_schema_version,
    }


def create_rule_draft(user, payload):
    if not isinstance(payload, dict):
        raise StructuredRuleError("请求体必须为对象")
    faculty_id = _authorize_admin(user, payload.get("faculty_id"))
    name = payload.get("name")
    category = payload.get("material_category")
    if not isinstance(name, str) or not name.strip() or category != "competition":
        raise StructuredRuleError("规则名称或材料类别无效")
    rule = Rule(
        name=name.strip(), type="academic", sub_type=category,
        score=_score(payload.get("score")), max_score=payload.get("max_score"),
        max_count=payload.get("max_count"), status="draft", faculty_id=faculty_id,
        description=payload.get("description"), match_terms=_terms(payload),
        match_schema_version=NORMALIZATION_VERSION, draft_version=1,
    )
    db.session.add(rule); db.session.commit()
    return rule


def preview_rule(user, rule):
    _authorize_admin(user, rule.faculty_id)
    snapshot = rule_snapshot(rule)
    from use_cases.cycles import current_cycle_policy
    policy = current_cycle_policy(required=True)
    snapshot["cycle_code"] = policy.cycle_code
    try:
        _validate_structured_snapshot(snapshot)
        conflicts = _find_overlapping_versions(rule, snapshot)
    except RulePublishingError as error:
        raise StructuredRuleError(str(error), code=error.code, details={
            "conflicts": error.conflicts,
        }) from error
    return {"rule": serialize_rule(rule), "cycle_code": policy.cycle_code,
            "conflicts": conflicts, "publishable": not conflicts}


def publish_draft(user, rule, expected_version):
    _authorize_admin(user, rule.faculty_id)
    if type(expected_version) is not int or expected_version <= 0:
        raise StructuredRuleError("必须提供有效草稿版本", code="invalid_version")
    changed = Rule.query.filter_by(
        id=rule.id, status="draft", draft_version=expected_version,
    ).update({"status": "active", "draft_version": Rule.draft_version + 1},
             synchronize_session=False)
    if not changed:
        db.session.rollback()
        raise StructuredRuleError("规则草稿版本已变化", code="source_version_conflict", status_code=409)
    rule = Rule.query.populate_existing().filter_by(id=rule.id).one()
    try:
        version, created = publish_rule_version(rule, published_by=user)
        db.session.commit()
    except RulePublishingError as error:
        db.session.rollback()
        raise StructuredRuleError(str(error), code=error.code, status_code=409,
                                  details={"conflicts": error.conflicts}) from error
    scan = scan_rule_coverage(user, cycle_code=version.snapshot.get("cycle_code"))
    db.session.commit()
    return rule, version, created, scan


def disable_rule(user, rule):
    _authorize_admin(user, rule.faculty_id)
    if rule.status == "disabled":
        return rule
    rule.status = "disabled"
    rule.draft_version += 1
    db.session.commit()
    return rule


def list_uncovered_terms(user):
    """Return privacy-safe aggregates; never material IDs, owners or attachments."""
    faculty_id = _authorize_admin(user)
    rows = MaterialRecord.query.filter_by(
        faculty_id=faculty_id, status="rule_unmatched"
    ).filter(MaterialRecord.normalized_terms.isnot(None)).all()
    grouped = {}
    for row in rows:
        terms = row.normalized_terms
        if not isinstance(terms, dict):
            continue
        safe_terms = {field: terms.get(field) for field in MATCH_FIELDS}
        key = (row.year, row.category, json.dumps(safe_terms, ensure_ascii=False,
                                                   sort_keys=True))
        item = grouped.setdefault(key, {
            "cycle_code": row.year, "faculty_id": faculty_id,
            "material_category": row.category, "normalized_terms": safe_terms,
            "affected_count": 0,
        })
        item["affected_count"] += 1
    return sorted(grouped.values(), key=lambda item: (
        -item["affected_count"], item["cycle_code"],
        json.dumps(item["normalized_terms"], ensure_ascii=False, sort_keys=True),
    ))


def scan_rule_coverage(user, *, cycle_code):
    """Idempotently expose a unique rule to students without submitting for them."""
    faculty_id = _authorize_admin(user)
    from use_cases.materials import match_material_rule, transition_material

    rows = MaterialRecord.query.filter_by(
        faculty_id=faculty_id, status="rule_unmatched"
    ).filter(MaterialRecord.normalized_terms.isnot(None)).with_for_update().all()
    available = []
    ambiguous = []
    for row in rows:
        result = match_material_rule(row, cycle_code)
        if result["status"] == "matched":
            transition_material(
                user, row, row.version, "mark_rule_available", "rule_available",
                details={"candidate_rule_version_id": result["match"]["version_id"]},
            )
            available.append(row.id)
        elif result["status"] == "ambiguous":
            ambiguous.append(row.id)
    return {
        "available_count": len(available),
        "ambiguous_count": len(ambiguous),
    }
