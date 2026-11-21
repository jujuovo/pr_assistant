"""Material evidence application use cases."""

import hashlib
import json
import mimetypes
from datetime import date
from pathlib import Path
import uuid
from sqlalchemy import func, or_

from automation_models import utcnow
from domain.materials import (
    ActorScope,
    MaterialPolicyError,
    MaterialScope,
    authorize_transition,
    allowed_actions as material_allowed_actions,
    can_view,
    is_owner,
    is_staff,
)
from extensions import db
from material_models import MaterialAttachment, MaterialEvent, MaterialRecord
from domain.student_work_scoring import POLICY_VERSION as WORK_POLICY
from models import Application, Faculty, Student
from services.materials.schemas import RESEARCH_TYPES, analyze, integer, normalize, object_keys
from workflow_models import CompetitionRulePackage, MaterialReviewCommand
from workflow_models import RuleVersion
from models import Rule
from domain.structured_rules import RuleCandidate, match_structured_rules
from domain.competition_rules import (
    CompetitionPackageError, competition_identity_keys, normalize_competition_facts,
    validate_competition_package,
)
from workflow_models import RecommendationCyclePolicy


def _ocr_links(row):
    from services.competition_ocr.binding import record_links
    return record_links(row)


class MaterialUseCaseError(ValueError):
    def __init__(self, message, *, code="invalid", status_code=400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


COMPETITION_CONTEXT_ACTIONS = {
    "student": ("view_catalog", "list_records", "create_draft"),
    "teacher": ("view_catalog", "list_pending", "review"),
    "admin": ("view_catalog", "list_records", "manage_rule_packages"),
}


REVIEW_ACTION_DECISIONS = {"competition_approved": "approve", "competition_returned": "return"}


def _latest_review_summaries(rows):
    """每条材料最近一次审核结论。

    列表页只给状态码时，教师看不出「这条是我通过了还是退回了」，
    所以结论、审核人、时间和意见必须随列表一起返回，不能靠前端再逐条回查。
    """
    from models import User

    record_ids = [row.id for row in rows]
    if not record_ids:
        return {}
    events = MaterialEvent.query.filter(
        MaterialEvent.record_id.in_(record_ids),
        MaterialEvent.action.in_(tuple(REVIEW_ACTION_DECISIONS)),
    ).order_by(MaterialEvent.id).all()
    if not events:
        return {}
    actors = {
        user.id: {"id": user.id, "name": user.name, "username": user.username, "role": user.role}
        for user in User.query.filter(
            User.id.in_({event.actor_id for event in events})
        ).all()
    }
    latest = {}
    for event in events:
        latest[event.record_id] = {
            "decision": REVIEW_ACTION_DECISIONS[event.action],
            "comment": (event.details or {}).get("comment"),
            "actor": actors.get(event.actor_id),
            "at": (event.created_at.isoformat() + "Z") if event.created_at else None,
        }
    return latest


def competition_workbench_summary(user):
    _package, context = competition_workflow_context(user)
    year = context["cycle"]["cycle_code"]
    query = MaterialRecord.query.filter_by(category="competition", year=year)
    successor_source_ids = db.session.query(MaterialRecord.supersedes_record_id).filter(
        MaterialRecord.category == "competition",
        MaterialRecord.year == year,
        MaterialRecord.supersedes_record_id.isnot(None),
        # 已放弃的补正稿不再隐藏原材料，否则教师端和学生端都会少看见这条材料。
        MaterialRecord.status != "abandoned",
    )
    if user.role == "student" and user.student_id:
        query = query.filter_by(student_id=user.student_id).filter(
            MaterialRecord.status != "abandoned"
        )
    elif user.role in {"teacher", "admin"} and user.faculty_id:
        query = query.filter_by(faculty_id=user.faculty_id)
        if user.role == "teacher":
            query = query.filter(
                or_(MaterialRecord.competition_rule_package_id.isnot(None),
                    MaterialRecord.rule_version_id.isnot(None)),
            )
    else:
        raise MaterialUseCaseError("当前账号无权读取竞赛工作台", code="forbidden", status_code=403)
    # 审核记录属于历史证据，不能因为学生开了补正稿就消失；
    # 只有「待审列表」才需要隐藏已被新版本取代的旧记录。
    history_query = query
    query = query.filter(~MaterialRecord.id.in_(successor_source_ids))
    counts = {status: count for status, count in query.with_entities(
        MaterialRecord.status, func.count(MaterialRecord.id)
    ).group_by(MaterialRecord.status).all()}
    rows = query.order_by(MaterialRecord.updated_at.desc(), MaterialRecord.id.desc()).limit(50).all()
    reviews = _latest_review_summaries(rows)
    def item(row):
        return {
            "id": row.id, "student_id": row.student_id, "status": row.status,
            "version": row.version, "project_name": (row.data or {}).get("project_name"),
            "competition_name": (row.data or {}).get("competition_name"),
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "review": reviews.get(row.id),
            "supersedes_record_id": row.supersedes_record_id,
            "superseded_by_record_id": superseded_by.get(row.id),
            "allowed_actions": list(material_allowed_actions(_actor_scope(user), _material_scope(row))),
        }
    pending_statuses = {"submitted", "under_review"}
    reviewed_statuses = {"needs_correction", "scored", "verified", "verified_not_eligible"}
    if user.role == "teacher":
        item_rows = [row for row in rows if row.status in pending_statuses]
        # 已审记录不受「被取代」影响：退回过的旧版本仍需留在审核记录里。
        reviewed_rows = history_query.filter(
            MaterialRecord.status.in_(tuple(reviewed_statuses))
        ).order_by(
            MaterialRecord.updated_at.desc(), MaterialRecord.id.desc()
        ).limit(50).all()
        reviews.update(_latest_review_summaries(reviewed_rows))
    else:
        item_rows = rows
        reviewed_rows = []
    # 同一项目补正后会出现新旧两条，必须告诉前端谁取代了谁，否则教师无法判断哪条算数。
    visible_ids = [row.id for row in item_rows] + [row.id for row in reviewed_rows]
    superseded_by = {}
    if visible_ids:
        for successor in MaterialRecord.query.filter(
            MaterialRecord.supersedes_record_id.in_(visible_ids),
            MaterialRecord.status != "abandoned",
        ).order_by(MaterialRecord.id).all():
            superseded_by[successor.supersedes_record_id] = successor.id
    return {
        "cycle_code": year,
        "role": user.role,
        "status_counts": counts,
        "pending_count": counts.get("submitted", 0) + counts.get("under_review", 0),
        "needs_correction_count": counts.get("needs_correction", 0),
        "completed_count": sum(counts.get(status, 0) for status in (
            "scored", "verified", "verified_not_eligible"
        )),
        "items": [item(row) for row in item_rows],
        "reviewed_items": [item(row) for row in reviewed_rows],
    }


def student_material_summary(user):
    """Count the student's current MaterialRecord workflow across every category."""
    if user.role != "student" or not user.student_id:
        raise MaterialUseCaseError("仅学生本人可读取材料统计", code="forbidden", status_code=403)
    successor_source_ids = db.session.query(MaterialRecord.supersedes_record_id).filter(
        MaterialRecord.student_id == user.student_id,
        MaterialRecord.supersedes_record_id.isnot(None),
        MaterialRecord.status != "abandoned",
    )
    counts = dict(
        db.session.query(MaterialRecord.status, func.count(MaterialRecord.id))
        .filter(
            MaterialRecord.student_id == user.student_id,
            MaterialRecord.application_id.is_(None),
            MaterialRecord.status != "abandoned",
            ~MaterialRecord.id.in_(successor_source_ids),
        )
        .group_by(MaterialRecord.status)
        .all()
    )
    approved = sum(counts.get(status, 0) for status in ("verified", "scored", "verified_not_eligible"))
    pending = counts.get("submitted", 0) + counts.get("under_review", 0)
    needs_correction = counts.get("needs_correction", 0)
    rejected = counts.get("rejected", 0)
    return {
        "status_counts": counts,
        "pending_count": pending,
        "approved_count": approved,
        "needs_correction_count": needs_correction,
        "rejected_count": rejected,
        "submitted_count": pending + approved + needs_correction + rejected,
    }


def teacher_noncompetition_summary(user):
    """Count reviewable non-competition materials in the teacher's own faculty."""
    if user.role not in {"teacher", "admin"} or not user.faculty_id:
        raise MaterialUseCaseError("仅本学院教师可读取非竞赛待审统计", code="forbidden", status_code=403)
    from services.materials.ocr_schemas import MANUAL_TYPES
    categories = tuple(MANUAL_TYPES | {"volunteer", "student_work"})
    counts = dict(
        db.session.query(MaterialRecord.status, func.count(MaterialRecord.id))
        .filter(
            MaterialRecord.faculty_id == user.faculty_id,
            MaterialRecord.category.in_(categories),
            MaterialRecord.application_id.is_(None),
            MaterialRecord.status != "abandoned",
        )
        .group_by(MaterialRecord.status)
        .all()
    )
    pending = counts.get("submitted", 0) + counts.get("under_review", 0)
    return {
        "status_counts": counts,
        "pending_count": pending,
        "needs_correction_count": counts.get("needs_correction", 0),
        "completed_count": sum(
            counts.get(status, 0)
            for status in ("verified", "scored", "verified_not_eligible")
        ),
    }


def competition_workflow_context(user, *, expected_digest=None):
    """Return the sole backend-authoritative context for competition UI flows."""
    actions = COMPETITION_CONTEXT_ACTIONS.get(getattr(user, "role", None))
    if actions is None or not getattr(user, "faculty_id", None):
        raise MaterialUseCaseError(
            "当前账号没有竞赛工作流权限", code="forbidden", status_code=403
        )

    cycle = RecommendationCyclePolicy.query.filter_by(status="active").one_or_none()
    if cycle is None:
        raise MaterialUseCaseError(
            "当前没有启用的推免周期，请联系管理员准备周期政策",
            code="competition_cycle_missing",
            status_code=409,
        )
    package = CompetitionRulePackage.query.filter_by(
        cycle_code=cycle.cycle_code, scope_key="global", status="current"
    ).one_or_none()
    if package is None:
        raise MaterialUseCaseError(
            f"{cycle.cycle_code} 周期没有可用的正式竞赛规则包，请联系管理员完成发布",
            code="competition_package_missing",
            status_code=409,
        )

    try:
        validated = validate_competition_package(package.snapshot)
    except CompetitionPackageError as error:
        raise MaterialUseCaseError(
            "当前正式竞赛规则包未通过完整性校验，请联系管理员重新发布",
            code="competition_package_invalid",
            status_code=409,
        ) from error
    expected_digest = (expected_digest or "").strip().strip('"')
    if expected_digest.startswith("W/"):
        expected_digest = expected_digest[2:].strip().strip('"')
    if expected_digest and expected_digest != package.digest:
        raise MaterialUseCaseError(
            "竞赛规则上下文版本已变化，请刷新后重新确认",
            code="competition_context_version_conflict",
            status_code=409,
        )
    if validated.cycle_code != cycle.cycle_code:
        raise MaterialUseCaseError(
            "启用周期与正式竞赛规则包不一致，请联系管理员修复配置",
            code="competition_context_cycle_mismatch",
            status_code=409,
        )

    catalog = [
        {
            "competition_id": item["competition_id"],
            "name": item["name"],
            "category": item["category"],
            "levels": item["levels"],
            "event_family": item["event_family"],
        }
        for item in package.snapshot["catalog"]
    ]
    return package, {
        "available": True,
        "cycle": {
            "cycle_code": cycle.cycle_code,
            "display_name": cycle.display_name,
            "policy_version": cycle.version,
            "eligible_award_start_date": cycle.eligible_award_start_date.isoformat(),
            "eligible_award_end_date": cycle.eligible_award_end_date.isoformat(),
        },
        "rule_package": {
            "id": package.id,
            "package_id": package.package_id,
            "version": package.version,
            "digest": package.digest,
            "scope_key": package.scope_key,
            "status": package.status,
        },
        "evidence_period": package.snapshot["evidence_period"],
        "catalog": {"count": len(catalog), "items": catalog},
        "field_schema": package.snapshot["field_schema"],
        "allowed_actions": list(actions),
    }


COMPETITION_REVIEW_FIELDS = frozenset(
    {"version", "decision", "comment", "idempotency_key"}
)

DERIVED_PRESENTATION_FIELDS = frozenset({
    "academic_specialty_total", "specialty_score",
    "comprehensive_performance_total", "performance_score",
    "total_score", "comprehensive_score", "total_comprehensive_score",
    "final_comprehensive_score", "final_score", "major_ranking",
    "ranking", "ranking_count", "total_students",
})


def _reject_derived_material_fields(data):
    if not isinstance(data, dict):
        raise MaterialUseCaseError("材料事实必须是对象", code="invalid_material_facts")
    forbidden = sorted(DERIVED_PRESENTATION_FIELDS.intersection(data))
    if forbidden:
        raise MaterialUseCaseError(
            f"材料请求不允许派生字段: {', '.join(forbidden)}",
            code="derived_fields_read_only",
        )


def validate_competition_review_command(user, row, payload):
    """Validate the intentionally narrow, server-authoritative review command.

    This function performs no writes.  Keeping the contract in the use-case
    layer ensures HTTP and future batch adapters cannot accidentally restore
    legacy rule selection or score override fields.
    """
    if row.category != "competition":
        raise MaterialUseCaseError("该审核命令仅适用于竞赛材料")
    if not isinstance(payload, dict):
        raise MaterialUseCaseError("审核请求必须是对象")
    unexpected = sorted(set(payload) - COMPETITION_REVIEW_FIELDS - {"ocr_confirmed"})
    missing = sorted((COMPETITION_REVIEW_FIELDS - {"comment"}) - set(payload))
    if unexpected:
        raise MaterialUseCaseError(
            f"竞赛审核不允许字段: {', '.join(unexpected)}",
            code="competition_review_forbidden_fields",
        )
    if missing:
        raise MaterialUseCaseError(
            f"竞赛审核缺少字段: {', '.join(missing)}",
            code="competition_review_invalid_command",
        )
    if user is None or user.role != "teacher" or not user.faculty_id:
        raise MaterialUseCaseError(
            "只有授权教师可以审核竞赛材料", code="forbidden", status_code=403
        )
    if user.faculty_id != row.faculty_id:
        raise MaterialUseCaseError(
            "无权审核其他学院的竞赛材料", code="forbidden", status_code=403
        )
    version = payload["version"]
    integer(version, "version", 1, 2_000_000_000)
    decision = payload["decision"]
    if decision not in {"approve", "return"}:
        raise MaterialUseCaseError(
            "竞赛审核动作只能是 approve 或 return",
            code="competition_review_invalid_decision",
        )
    comment = payload.get("comment", "")
    if not isinstance(comment, str) or len(comment) > 2000 or (decision == "return" and not comment.strip()):
        raise MaterialUseCaseError(
            "审核意见不得超过2000字符，退回修改时必须填写原因",
            code="competition_review_comment_required",
        )
    key = payload["idempotency_key"]
    if not isinstance(key, str) or not 1 <= len(key) <= 128:
        raise MaterialUseCaseError("幂等键必须为1至128字符")
    if "ocr_confirmed" in payload and type(payload["ocr_confirmed"]) is not bool:
        raise MaterialUseCaseError("OCR人工确认必须为布尔值", code="invalid_ocr_confirmation")
    return {
        **({"ocr_confirmed":payload["ocr_confirmed"]} if "ocr_confirmed" in payload else {}),
        "version": version,
        "decision": decision,
        "comment": comment.strip(),
        "idempotency_key": key,
    }


def competition_review_context(user, row):
    """Build the immutable evidence/rule projection used by reviewers."""
    from services.competition_ocr.assessment import assessment
    if row.category != "competition":
        raise MaterialUseCaseError("该审核上下文仅适用于竞赛材料")
    if user is None or user.role != "teacher" or not user.faculty_id:
        raise MaterialUseCaseError(
            "只有授权教师可以查看竞赛审核上下文", code="forbidden", status_code=403
        )
    if user.faculty_id != row.faculty_id:
        raise MaterialUseCaseError(
            "无权查看其他学院的竞赛材料", code="forbidden", status_code=403
        )
    readable_statuses = {
        "submitted", "under_review", "needs_correction", "scored",
        "verified", "verified_not_eligible",
    }
    if row.status not in readable_statuses:
        raise MaterialUseCaseError(
            "材料不在可审核或历史查看状态", code="review_not_available", status_code=409
        )
    package = db.session.get(CompetitionRulePackage, row.competition_rule_package_id)
    if package is None:
        raise MaterialUseCaseError(
            "材料缺少固定竞赛规则包", code="rule_package_missing", status_code=409
        )
    facts = dict(row.confirmed_terms or {})
    competition_id = facts.get("competition_id")
    item = next(
        (entry for entry in package.snapshot["catalog"]
         if entry["competition_id"] == competition_id),
        None,
    )
    if item is None:
        raise MaterialUseCaseError(
            "固定规则包中不存在该竞赛", code="rule_package_invalid", status_code=409
        )
    return {
        "record_id": row.id,
        "material_version": row.version,
        "status": row.status,
        "attachments": [
            {
                "id": attachment.id,
                "filename": attachment.filename,
                "size": attachment.size,
                "sha256": attachment.sha256,
                "media_type": mimetypes.guess_type(attachment.filename)[0] or "application/octet-stream",
                "url": (
                    f"/api/materials/competition/records/{row.id}/attachments/"
                    f"{attachment.id}"
                ),
                "preview_url": (
                    f"/api/materials/competition/records/{row.id}/attachments/"
                    f"{attachment.id}?inline=1"
                ),
            }
            for attachment in row.attachments
        ],
        "ocr_raw_terms": row.ocr_raw_terms,
        "ocr_assessment": assessment(row),
        "ocr_links": _ocr_links(row),
        "confirmed_terms": facts,
        "rule_basis": {
            "package_id": package.package_id,
            "package_version": package.version,
            "package_digest": package.digest,
            "competition_id": item["competition_id"],
            "competition_name": item["name"],
            "category": item["category"],
            "event_family": item["event_family"],
            "evidence_period": package.snapshot["evidence_period"],
        },
        "candidate_score": (row.analysis or {}).get("candidate_score"),
        "candidate_score_authority": "server",
        "history": _material_history(row),
        "allowed_actions": (
            ["approve", "return"]
            if row.status in {"submitted", "under_review"} else []
        ),
        "review_command_schema": {
            "writable_fields": ["version", "decision", "comment", "idempotency_key"],
            "decisions": ["approve", "return"],
        },
    }


def _material_history(row):
    """材料审核轨迹：谁、何时、做了什么、写了什么意见。

    审核人是审核结论的一部分，缺了它教师无法判断这条记录由谁负责。
    """
    from models import User

    events = sorted(row.events, key=lambda event: (event.created_at, event.id))
    actor_ids = {event.actor_id for event in events if event.actor_id}
    actors = {
        user.id: {"id": user.id, "name": user.name, "username": user.username, "role": user.role}
        for user in User.query.filter(User.id.in_(actor_ids)).all()
    } if actor_ids else {}
    return [{
        "action": event.action,
        "comment": (event.details or {}).get("comment"),
        "actor": actors.get(event.actor_id),
        "created_at": (event.created_at.isoformat() + "Z") if event.created_at else None,
    } for event in events]


def _actor_scope(user):
    return ActorScope(user.role, user.student_id, user.faculty_id)


def _material_scope(row):
    return MaterialScope(row.student_id, row.faculty_id, row.status)


def _authorize_transition(user, row, action, target_status):
    try:
        authorize_transition(_actor_scope(user), _material_scope(row), action, target_status)
    except MaterialPolicyError as error:
        actor_scope = _actor_scope(user)
        material_scope = _material_scope(row)
        visible = can_view(actor_scope, material_scope)
        role_allows_action = (
            is_staff(actor_scope, material_scope)
            if action == "review"
            else is_owner(actor_scope, material_scope)
        )
        raise MaterialUseCaseError(
            str(error),
            code="invalid_transition" if visible and role_allows_action else "forbidden",
            status_code=409 if visible and role_allows_action else 403,
        ) from error


def _event(row, user, action, details):
    db.session.add(
        MaterialEvent(
            record_id=row.id,
            actor_id=user.id,
            action=action,
            details=details,
        )
    )


def _cas_change(row, version, allowed_statuses, changes):
    integer(version, "version", 1, 2_000_000_000)
    changed = (
        MaterialRecord.query.filter_by(id=row.id, version=version)
        .filter(MaterialRecord.status.in_(allowed_statuses))
        .update(
            {**changes, "version": MaterialRecord.version + 1, "updated_at": utcnow()},
            synchronize_session=False,
        )
    )
    if not changed:
        raise MaterialUseCaseError(
            "材料状态或版本已变化，请刷新后重试",
            code="version_conflict",
            status_code=409,
        )
    db.session.refresh(row)


def transition_material(user, row, version, action, target_status, *, details=None):
    """Apply one policy-authorized state transition without owning the transaction."""
    _authorize_transition(user, row, action, target_status)
    previous = row.status
    _cas_change(row, version, (previous,), {"status": target_status})
    _event(row, user, action, {
        "from_status": previous, "to_status": target_status,
        "version": row.version, **(details or {}),
    })
    return row


def match_material_rule(row, cycle_code):
    pairs = (
        db.session.query(RuleVersion, Rule)
        .join(Rule, Rule.id == RuleVersion.rule_id)
        .filter(RuleVersion.status == "published", Rule.status == "active")
        .all()
    )
    latest = {}
    for version, rule in pairs:
        snapshot = version.snapshot
        if not isinstance(snapshot.get("match_terms"), dict):
            continue
        if snapshot.get("cycle_code") != cycle_code:
            continue
        previous = latest.get(rule.id)
        if previous is None or version.version > previous[0].version:
            latest[rule.id] = (version, rule)
    candidates = [RuleCandidate(
        version_id=version.id,
        cycle_code=version.snapshot.get("cycle_code"),
        faculty_id=version.snapshot.get("faculty_id"),
        material_category=version.snapshot.get("sub_type"),
        terms=version.snapshot.get("match_terms"),
        score=version.snapshot.get("score"),
    ) for version, _rule in latest.values()]
    return match_structured_rules(
        candidates, cycle_code=cycle_code, faculty_id=row.faculty_id,
        material_category=row.category, terms=row.normalized_terms,
    )


def create_material(user, category, payload):
    object_keys(payload, {"year", "data", "application_id", "manual_only"}, {"year", "data"})
    if user.role != "student" or not user.student_id:
        raise MaterialUseCaseError("仅学生本人可创建申报材料", code="forbidden", status_code=403)
    manual_only = payload.get("manual_only", False)
    if type(manual_only) is not bool:
        raise MaterialUseCaseError("manual_only必须为布尔值")
    if manual_only:
        from services.materials.ocr_schemas import MANUAL_TYPES
        if category not in MANUAL_TYPES | {"student_work"}:
            raise MaterialUseCaseError("该类别请使用其正式申报通道")
    _reject_derived_material_fields(payload["data"])
    owner = Student.query.filter_by(student_id=user.student_id).first()
    if not owner or not owner.faculty_id or owner.faculty_id != user.faculty_id:
        raise MaterialUseCaseError("学生账号未正确关联学院")
    work_policy = (category == "student_work" and integer(payload["year"], "year", 2000, 2100) >= 2028
                   and db.session.get(Faculty, owner.faculty_id).name == "信息学院")
    if work_policy:
        manual_only = False
        if payload.get("application_id") is not None:
            raise MaterialUseCaseError("干部任职使用独立材料申报")
    application_id = payload.get("application_id")
    if category in RESEARCH_TYPES | {"innovation_training"} and application_id is not None:
        raise MaterialUseCaseError("科研成果使用独立材料申报")
    competition_package = None
    if category == "competition":
        if application_id is not None:
            raise MaterialUseCaseError(
                "竞赛材料不能关联旧申请链路",
                code="competition_material_route_required", status_code=409,
            )
        requested_year = integer(payload["year"], "year", 2000, 2100)
        competition_package = CompetitionRulePackage.query.filter_by(
            cycle_code=requested_year, scope_key="global", status="current"
        ).one_or_none()
        if competition_package is None:
            raise MaterialUseCaseError(
                "当前周期没有正式竞赛规则包",
                code="competition_package_unavailable", status_code=409,
            )
    if application_id is not None:
        integer(application_id, "application_id", 1, 2_000_000_000)
        application = (
            Application.query.filter_by(id=application_id).with_for_update().first()
        )
        if not application:
            raise MaterialUseCaseError("关联申请不存在", code="not_found", status_code=404)
        if application.student_id != user.student_id or application.faculty_id != owner.faculty_id:
            raise MaterialUseCaseError("不能关联其他学生的申请", code="forbidden", status_code=403)
    if category == "competition":
        try:
            normalized = normalize_competition_facts(competition_package.snapshot, payload["data"])
        except CompetitionPackageError as error:
            raise MaterialUseCaseError(str(error), code=error.code) from error
    else:
        normalized = normalize(category, payload["data"])
    row = MaterialRecord(
        student_id=user.student_id,
        faculty_id=owner.faculty_id,
        category=category,
        year=integer(payload["year"], "year", 2000, 2100),
        application_id=application_id,
        data=normalized,
        analysis=(
            {"candidate_score": normalized["candidate_score"], "authority": "server"}
            if category == "competition" else analyze(category, normalized)
        ),
        confirmed_terms=(dict(normalized) if category == "competition" else None),
        normalized_terms=(dict(normalized) if category == "competition" else None),
        normalization_version=("competition-facts-v1" if category == "competition" else None),
        status="draft",
        competition_rule_package_id=(competition_package.id if competition_package else None),
    )
    if work_policy:
        row.normalization_version = WORK_POLICY
    if manual_only:
        row.analysis = {**row.analysis, "manual_only":True}
    db.session.add(row)
    db.session.flush()
    _event(row, user, "created", {"version": row.version})
    return row


def edit_material(user, row, version, data):
    _authorize_transition(user, row, "edit", "draft")
    _reject_derived_material_fields(data)
    if row.category == "competition":
        package = db.session.get(CompetitionRulePackage, row.competition_rule_package_id)
        if package is None:
            raise MaterialUseCaseError("竞赛规则包不存在", code="rule_package_changed", status_code=409)
        try:
            normalized = normalize_competition_facts(package.snapshot, data)
        except CompetitionPackageError as error:
            raise MaterialUseCaseError(str(error), code=error.code) from error
    else:
        normalized = normalize(row.category, data)
    _cas_change(
        row,
        version,
        ("draft", "rule_unmatched", "rule_available", "needs_correction"),
        {
            "data": normalized,
            "analysis": ({"candidate_score": normalized["candidate_score"], "authority": "server"}
                         if row.category == "competition" else {**analyze(row.category, normalized),
                             **({"manual_only":True} if (row.analysis or {}).get("manual_only") else {})}),
            "confirmed_terms": (dict(normalized) if row.category == "competition" else row.confirmed_terms),
            "normalized_terms": (dict(normalized) if row.category == "competition" else row.normalized_terms),
            "check_report": None,
            "ocr_raw_terms": None,
            "status": "draft",
            "rule_version_id": None,
        },
    )
    _event(row, user, "edited", {"version": row.version, "data": normalized})
    return row


def submit_material(user, row, version):
    from use_cases.cycles import current_cycle_policy, pin_material_cycle
    _authorize_transition(user, row, "submit", "submitted")
    if row.category == "volunteer":
        from services.volunteer_ocr import assert_gate
        assert_gate(row)
    from services.materials.originals import verify_ocr_originals
    verify_ocr_originals(row)
    policy = current_cycle_policy(required=True)
    if row.category in RESEARCH_TYPES | {"innovation_training"} or row.normalization_version == WORK_POLICY:
        from domain.research_scoring import POLICY_VERSION
        if not row.attachments or policy.cycle_code < 2028 or row.year != policy.cycle_code:
            raise MaterialUseCaseError("需要提交证明并选择适用的2028届或以后周期")
        if row.category == "innovation_training":
            from domain.innovation_scoring import POLICY_VERSION
        row.normalization_version = WORK_POLICY if row.category == "student_work" else POLICY_VERSION
    if row.category != "competition":
        from use_cases.scoring import match_published_rule
        legacy_match = match_published_rule(row, cycle_code=policy.cycle_code)
        if legacy_match["status"] != "matched":
            raise MaterialUseCaseError(
                "材料没有唯一适用的已发布规则",
                code=("ambiguous_scoring_rules" if legacy_match["status"] == "ambiguous"
                      else "material_terms_unmapped"), status_code=409,
            )
        policy = pin_material_cycle(row)
        _cas_change(row, version, ("draft",), {
            "status": "submitted", "year": policy.cycle_code,
            "cycle_policy_version_id": policy.id,
            "rule_version_id": legacy_match["version"].id,
        })
        _event(row, user, "submitted", {
            "version": row.version, "cycle_code": policy.cycle_code,
            "cycle_policy_version_id": policy.id,
            "rule_version_id": legacy_match["version"].id,
        })
        return row
    package = db.session.get(CompetitionRulePackage, row.competition_rule_package_id)
    current = CompetitionRulePackage.query.filter_by(
        cycle_code=policy.cycle_code, scope_key="global", status="current"
    ).one_or_none()
    if package is None or current is None or package.id != current.id:
        raise MaterialUseCaseError(
            "竞赛规则包已变化，请刷新并重新确认",
            code="rule_package_changed", status_code=409,
        )
    if not row.attachments:
        raise MaterialUseCaseError(
            "竞赛材料至少需要一个证明附件", code="competition_attachment_required"
        )
    try:
        source_facts = {
            key: value for key, value in (row.confirmed_terms or {}).items()
            if key in {
                "competition_id", "project_name", "award_date", "level", "award",
                "event_year", "participation_mode", "team_size", "personal_rank",
                "event_format", "csp_percentile", "group", "track", "evidence",
            }
        }
        normalized = normalize_competition_facts(package.snapshot, source_facts)
    except CompetitionPackageError as error:
        raise MaterialUseCaseError(str(error), code=error.code) from error
    row.data = dict(normalized)
    row.confirmed_terms = dict(normalized)
    row.normalized_terms = dict(normalized)
    duplicate_digest, work_key, event_key = competition_identity_keys(
        package.snapshot, normalized
    )
    duplicate = (
        MaterialRecord.query.filter_by(
            student_id=row.student_id, year=policy.cycle_code,
            competition_duplicate_digest=duplicate_digest,
        )
        .filter(MaterialRecord.id != row.id)
        .first()
    )
    if duplicate is not None:
        raise MaterialUseCaseError(
            "相同竞赛材料已经提交", code="duplicate_submission", status_code=409
        )
    _authorize_transition(user, row, "submit", "submitted")
    policy = pin_material_cycle(row)
    _cas_change(
        row,
        version,
        ("draft",),
        {
            "status": "submitted",
            "year": policy.cycle_code,
            "cycle_policy_version_id": policy.id,
            "rule_version_id": None,
            "competition_rule_package_id": package.id,
            "competition_duplicate_digest": duplicate_digest,
            "competition_work_group_key": work_key,
            "competition_event_group_key": event_key,
        },
    )
    _event(
        row,
        user,
        "submitted",
        {"version": row.version, "cycle_code": policy.cycle_code,
         "cycle_policy_version_id": policy.id,
         "competition_rule_package_id": package.id,
         "competition_rule_package_digest": package.digest},
    )
    return row


def confirm_available_rule(user, row, version, expected_rule_version_id, confirmed):
    if confirmed is not True:
        raise MaterialUseCaseError(
            "必须确认规则和申报信息后才能重新提交",
            code="student_confirmation_required", status_code=409,
        )
    integer(expected_rule_version_id, "rule_version_id", 1, 2_000_000_000)
    _authorize_transition(user, row, "confirm_submit", "submitted")
    if row.category == "volunteer":
        from services.volunteer_ocr import assert_gate
        from services.materials.originals import verify_ocr_originals
        assert_gate(row)
        verify_ocr_originals(row)
    from use_cases.cycles import current_cycle_policy, pin_material_cycle
    policy = current_cycle_policy(required=True)
    result = match_material_rule(row, policy.cycle_code)
    if result["status"] != "matched":
        raise MaterialUseCaseError(
            "当前材料不再唯一匹配该规则，请刷新后重试",
            code=result.get("reason") or "rule_match_changed", status_code=409,
        )
    match = result["match"]
    if match["version_id"] != expected_rule_version_id:
        raise MaterialUseCaseError(
            "计分规则版本已变化，请重新确认",
            code="source_version_conflict", status_code=409,
        )
    policy = pin_material_cycle(row)
    _cas_change(row, version, ("rule_available",), {
        "status": "submitted", "year": policy.cycle_code,
        "cycle_policy_version_id": policy.id,
        "rule_version_id": expected_rule_version_id,
    })
    _event(row, user, "confirmed_rule_and_submitted", {
        "version": row.version, "rule_version_id": expected_rule_version_id,
        "cycle_code": policy.cycle_code, "candidate_score": match.get("score"),
    })
    published = db.session.get(RuleVersion, expected_rule_version_id)
    return row, {
        "rule_version_id": expected_rule_version_id,
        "rule_name": published.snapshot.get("name") if published else None,
        "candidate_score": match.get("score"),
        "match_terms": published.snapshot.get("match_terms") if published else None,
    }


def _inherit_attachments(source, target):
    """补正/重确认版本继承原件。

    学生只是改了一个日期，不应该被要求重新上传扫描件；证据跟着材料版本走，
    复制文件而不是共用存储名，避免任一版本被删除时另一个版本丢失原件。
    """
    import shutil

    from services.materials.service import stored_path

    inherited = []
    for attachment in source.attachments:
        origin = stored_path(attachment.stored_name)
        if not origin.is_file():
            continue
        stored_name = uuid.uuid4().hex + Path(attachment.filename).suffix.lower()
        destination = stored_path(stored_name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, destination)
        db.session.add(MaterialAttachment(
            record_id=target.id, filename=attachment.filename, stored_name=stored_name,
            sha256=attachment.sha256, size=attachment.size,
        ))
        inherited.append(attachment.filename)
    return inherited


def create_correction_version(user, row, version, confirmed_terms):
    if not is_owner(_actor_scope(user), _material_scope(row)):
        raise MaterialUseCaseError("只能补正本人材料", code="forbidden", status_code=403)
    if row.status not in {
        "submitted", "under_review", "needs_correction",
        "verified_not_eligible", "scored", "verified",
    }:
        raise MaterialUseCaseError(
            "当前材料状态不允许创建补正版本",
            code="invalid_transition", status_code=409,
        )
    integer(version, "version", 1, 2_000_000_000)
    if row.version != version:
        raise MaterialUseCaseError(
            "材料版本已变化，请刷新后重试", code="version_conflict", status_code=409
        )
    successor = MaterialRecord.query.filter(
        MaterialRecord.supersedes_record_id == row.id,
        MaterialRecord.status != "abandoned",
    ).first()
    if successor is not None:
        raise MaterialUseCaseError(
            "该退回材料已经创建补正版本，请继续处理现有补正稿",
            code="correction_already_exists", status_code=409,
        )
    if row.category in RESEARCH_TYPES | {"innovation_training"} or row.normalization_version == WORK_POLICY:
        if row.status not in {"needs_correction", "verified_not_eligible", "scored"}:
            raise MaterialUseCaseError("当前材料不能补正", status_code=409)
        _cas_change(row, version, (row.status,), {})
        corrected = create_material(user, row.category, {"year": row.year, "data": confirmed_terms})
        corrected.supersedes_record_id = row.id
        corrected.correction_sequence = (row.correction_sequence or 0) + 1
        _event(corrected, user, "correction_version_created", {"supersedes_record_id": row.id})
        return corrected
    if row.category == "competition":
        if row.status != "needs_correction":
            raise MaterialUseCaseError(
                "只有退回的竞赛材料可以创建新版本",
                code="invalid_transition", status_code=409,
            )
        package = db.session.get(CompetitionRulePackage, row.competition_rule_package_id)
        current = CompetitionRulePackage.query.filter_by(
            cycle_code=row.year, scope_key="global", status="current"
        ).one_or_none()
        if package is None or current is None or package.id != current.id:
            raise MaterialUseCaseError(
                "竞赛规则包已变化，请走重新确认流程",
                code="rule_package_changed", status_code=409,
            )
        try:
            normalized = normalize_competition_facts(package.snapshot, confirmed_terms)
        except CompetitionPackageError as error:
            raise MaterialUseCaseError(str(error), code=error.code) from error
        corrected = MaterialRecord(
            student_id=row.student_id, faculty_id=row.faculty_id,
            category="competition", year=row.year, status="draft",
            data=dict(normalized), analysis={
                "candidate_score": normalized["candidate_score"], "authority": "server"
            },
            ocr_raw_terms=row.ocr_raw_terms,
            confirmed_terms=dict(normalized), normalized_terms=dict(normalized),
            normalization_version="competition-facts-v1",
            competition_rule_package_id=package.id,
            supersedes_record_id=row.id,
            correction_sequence=(row.correction_sequence or 0) + 1,
        )
        # Returned history remains readable, while its exact-submission lock is
        # released so the corrected version can be submitted.
        row.competition_duplicate_digest = None
        db.session.add(corrected); db.session.flush()
        inherited = _inherit_attachments(row, corrected)
        _event(corrected, user, "competition_correction_version_created", {
            "supersedes_record_id": row.id,
            "previous_status": row.status,
            "previous_version": row.version,
            "return_events_preserved": True,
            "inherited_attachments": inherited,
        })
        return corrected
    from domain.material_terms import (
        NORMALIZATION_VERSION, TermNormalizationError, normalize_confirmed_terms,
    )
    try:
        normalized_terms = normalize_confirmed_terms(confirmed_terms)
    except TermNormalizationError as error:
        raise MaterialUseCaseError(str(error), code="invalid_confirmed_terms") from error
    if not normalized_terms.get("award_date"):
        raise MaterialUseCaseError("补正版本必须确认获奖日期", code="award_date_required")
    new_data = dict(row.data or {})
    new_data["award_date"] = normalized_terms["award_date"]
    corrected = MaterialRecord(
        student_id=row.student_id, faculty_id=row.faculty_id,
        application_id=row.application_id, category=row.category, year=row.year,
        cycle_policy_version_id=row.cycle_policy_version_id,
        status="draft", data=new_data, analysis=dict(row.analysis or {}),
        ocr_raw_terms=row.ocr_raw_terms,
        confirmed_terms=dict(confirmed_terms), normalized_terms=normalized_terms,
        normalization_version=NORMALIZATION_VERSION,
        rule_version_id=None, supersedes_record_id=row.id,
        correction_sequence=(row.correction_sequence or 0) + 1,
    )
    db.session.add(corrected); db.session.flush()
    result = match_material_rule(corrected, row.year)
    if result["status"] == "ambiguous":
        raise MaterialUseCaseError(
            "补正材料同时匹配多条规则", code="ambiguous_scoring_rules", status_code=409
        )
    corrected.status = "rule_available" if result["status"] == "matched" else "rule_unmatched"
    _event(corrected, user, "correction_version_created", {
        "supersedes_record_id": row.id,
        "previous_status": row.status,
        "previous_version": row.version,
        "award_date": normalized_terms["award_date"],
        "rule_match_status": result["status"],
        "candidate_rule_version_id": (
            result["match"]["version_id"] if result["status"] == "matched" else None
        ),
    })
    return corrected


def reconfirm_competition_rule(user, row, version, confirmed_terms, confirmed):
    if not is_owner(_actor_scope(user), _material_scope(row)):
        raise MaterialUseCaseError("只能重新确认本人材料", code="forbidden", status_code=403)
    if row.category != "competition" or row.status != "rule_reconfirmation_required":
        raise MaterialUseCaseError("材料不在规则重新确认状态", code="invalid_transition", status_code=409)
    if confirmed is not True:
        raise MaterialUseCaseError("必须确认新规则快照", code="student_confirmation_required", status_code=409)
    if row.version != integer(version, "version", 1, 2_000_000_000):
        raise MaterialUseCaseError("材料版本已变化", code="version_conflict", status_code=409)
    package = CompetitionRulePackage.query.filter_by(
        cycle_code=row.year, scope_key="global", status="current"
    ).one_or_none()
    if package is None:
        raise MaterialUseCaseError("当前竞赛规则包不存在", code="rule_package_changed", status_code=409)
    try:
        normalized = normalize_competition_facts(package.snapshot, confirmed_terms)
        duplicate_digest, work_key, event_key = competition_identity_keys(package.snapshot, normalized)
    except CompetitionPackageError as error:
        raise MaterialUseCaseError(str(error), code=error.code) from error
    duplicate = MaterialRecord.query.filter_by(
        student_id=row.student_id, year=row.year,
        competition_duplicate_digest=duplicate_digest,
    ).filter(MaterialRecord.id != row.id).first()
    if duplicate:
        raise MaterialUseCaseError("相同竞赛材料已经提交", code="duplicate_submission", status_code=409)
    replacement = MaterialRecord(
        student_id=row.student_id, faculty_id=row.faculty_id, category="competition",
        year=row.year, cycle_policy_version_id=row.cycle_policy_version_id,
        status="submitted", data=dict(normalized),
        analysis={"candidate_score": normalized["candidate_score"], "authority": "server"},
        ocr_raw_terms=row.ocr_raw_terms, confirmed_terms=dict(normalized),
        normalized_terms=dict(normalized), normalization_version="competition-facts-v1",
        competition_rule_package_id=package.id,
        competition_duplicate_digest=duplicate_digest,
        competition_work_group_key=work_key, competition_event_group_key=event_key,
        supersedes_record_id=row.id, correction_sequence=(row.correction_sequence or 0) + 1,
    )
    db.session.add(replacement); db.session.flush()
    inherited = _inherit_attachments(row, replacement)
    _event(replacement, user, "competition_rule_reconfirmed", {
        "supersedes_record_id": row.id, "old_package_id": row.competition_rule_package_id,
        "new_package_id": package.id, "old_material_version": row.version,
        "new_material_version": replacement.version,
        "inherited_attachments": inherited,
    })
    return replacement


def withdraw_material(user, row, version):
    _authorize_transition(user, row, "withdraw", "draft")
    _cas_change(
        row,
        version,
        ("submitted",),
        {"status": "draft", "check_report": None},
    )
    _event(row, user, "withdrawn", {"version": row.version})
    return row


def abandon_returned_competition(user, row, version):
    if row.category != "competition":
        raise MaterialUseCaseError("仅竞赛材料支持放弃", code="invalid_category")
    transition_material(
        user, row, version, "abandon", "abandoned",
        details={"history_preserved": True},
    )
    row.competition_duplicate_digest = None
    return row


def add_attachments(user, row, version, files, storage_root):
    """Persist prepared ``(filename, bytes)`` attachments without committing."""
    _authorize_transition(user, row, "add_attachment", "draft")
    if not 1 <= len(files) <= 10 or len(row.attachments) + len(files) > 10:
        raise MaterialUseCaseError("每条材料最多10个附件")
    root = Path(storage_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    _cas_change(
        row,
        version,
        ("draft", "needs_correction"),
        {"status": "draft", "check_report": None},
    )
    created = []
    try:
        for filename, payload in files:
            suffix = Path(filename).suffix.lower()
            stored_name = uuid.uuid4().hex + suffix
            path = (root / stored_name).resolve()
            if path.parent != root:
                raise MaterialUseCaseError("无效材料路径")
            created.append(path)
            with path.open("xb") as output:
                output.write(payload)
            db.session.add(
                MaterialAttachment(
                    record_id=row.id,
                    filename=filename,
                    stored_name=stored_name,
                    sha256=hashlib.sha256(payload).hexdigest(),
                    size=len(payload),
                )
            )
        _event(
            row,
            user,
            "attachments_added",
            {"version": row.version, "filenames": [name for name, _ in files]},
        )
        db.session.flush()
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    db.session.expire(row, ["attachments"])
    return row, tuple(created)


def review_material(user, row, version, decision, comment, idempotency_key,
                    override_score=None, override_reason=None):
    if decision not in {"verified", "rejected", "needs_correction"}:
        raise MaterialUseCaseError("无效核验结论")
    if not isinstance(comment, str) or len(comment) > 2000:
        raise MaterialUseCaseError("核验说明必须为不超过2000字符的文字")
    if row.category == 'volunteer' and decision != 'verified' and not comment.strip():
        raise MaterialUseCaseError('退回或不通过必须填写原因')
    if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128:
        raise MaterialUseCaseError("幂等键必须为1至128字符")
    payload = {
        "record_id": row.id,
        "version": version,
        "decision": decision,
        "comment": comment.strip(),
        "actor_id": user.id,
        "override_score": override_score,
        "override_reason": override_reason,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    previous = MaterialReviewCommand.query.filter_by(
        record_id=row.id, idempotency_key=idempotency_key
    ).first()
    if previous:
        if previous.request_digest != digest:
            raise MaterialUseCaseError(
                "同一幂等键不能用于不同审核请求",
                code="idempotency_conflict",
                status_code=409,
            )
        db.session.refresh(row)
        return row, True

    if version != row.version:
        raise MaterialUseCaseError(
            "材料状态或版本已变化，请刷新后重试",
            code="version_conflict", status_code=409,
        )
    if row.status not in {"submitted", "under_review"} or row.rule_version_id is None:
        raise MaterialUseCaseError(
            "材料尚未正式提交并固定唯一规则版本",
            code="review_not_available", status_code=403,
        )

    # Authorize before loading policy details so unauthorized actors learn nothing.
    _authorize_transition(user, row, "review", decision)
    if row.category == 'volunteer' and decision == 'verified':
        from services.volunteer_ocr import assert_gate
        assert_gate(row)
        from services.materials.originals import verify_ocr_originals
        verify_ocr_originals(row)
    eligibility = None
    target_status = decision
    if decision == "verified":
        from domain.cycles import evaluate_award_date
        from workflow_models import RecommendationCyclePolicy

        policy = db.session.get(RecommendationCyclePolicy, row.cycle_policy_version_id)
        if policy is None:
            raise MaterialUseCaseError(
                "材料缺少固定周期政策", code="cycle_policy_missing", status_code=409
            )
        raw_award_date = row.data.get("award_date")
        try:
            award_date = date.fromisoformat(raw_award_date) if raw_award_date else None
        except (TypeError, ValueError):
            award_date = None
        eligibility = evaluate_award_date(
            award_date,
            policy.eligible_award_start_date,
            policy.eligible_award_end_date,
        )
        if eligibility.status == "needs_correction":
            target_status = "needs_correction"
    if target_status != decision:
        _authorize_transition(user, row, "review", target_status)
    _cas_change(row, version, ("submitted",), {"status": target_status})
    if decision == "verified":
        from use_cases.review_scoring import review_scoring_result

        cycle = {
            "cycle_code": policy.cycle_code,
            "policy_version": policy.version,
            "cycle_policy_version_id": policy.id,
        }
        eligibility_data = {
            "status": eligibility.status,
            "reason": eligibility.reason,
            "award_date": raw_award_date,
            "start_date": policy.eligible_award_start_date.isoformat(),
            "end_date": policy.eligible_award_end_date.isoformat(),
            "boundary": policy.boundary,
        }
        if eligibility.status == "eligible":
            from use_cases.scoring import score_verified_material

            score = score_verified_material(
                row, idempotency_key, actor=user, override_score=override_score,
                override_reason=override_reason,
            )
            scoring_status = score["status"]
            if scoring_status == "needs_rule":
                # Verification attempt is audited, but the source remains resumable.
                row.status = "submitted"
            elif scoring_status == "scored":
                row.status = "scored"
            scoring_result = review_scoring_result(
                overall_status="complete" if scoring_status == "scored" else "blocked",
                verification_status="verified",
                scoring_status=scoring_status,
                cycle=cycle,
                eligibility=eligibility_data,
                scoring=score,
                snapshot={"snapshot_id": score.get("snapshot_id")} if score.get("snapshot_id") else None,
                allowed_actions=[] if scoring_status == "scored" else ["publish_rule", "retry_scoring"],
            )
        elif eligibility.status == "not_eligible":
            row.status = "verified_not_eligible"
            scoring_result = review_scoring_result(
                overall_status="complete",
                verification_status="verified",
                scoring_status="verified_not_eligible",
                cycle=cycle,
                eligibility=eligibility_data,
                scoring=None,
                snapshot=None,
                allowed_actions=["view"],
            )
        else:
            scoring_result = review_scoring_result(
                overall_status="blocked",
                verification_status="verified",
                scoring_status="needs_correction",
                cycle=cycle,
                eligibility=eligibility_data,
                scoring=None,
                snapshot=None,
                allowed_actions=["correct_evidence", "resubmit"],
            )
    else:
        from use_cases.review_scoring import review_scoring_result
        scoring_result = review_scoring_result(
            overall_status="complete",
            verification_status=decision,
            scoring_status="not_scored",
            allowed_actions=["correct_evidence", "resubmit"] if decision == "needs_correction" else ["view"],
        )
    details = {
        "version": row.version,
        "decision": decision,
        "comment": comment.strip(),
        "idempotency_key": idempotency_key,
        "data_snapshot": row.data,
        "check_report_snapshot": row.check_report,
        "ocr_links_snapshot": _ocr_links(row),
        "attachments_snapshot": [
            {
                "id": attachment.id,
                "filename": attachment.filename,
                "size": attachment.size,
                "sha256": attachment.sha256,
            }
            for attachment in row.attachments
        ],
        "scoring": scoring_result,
    }
    _event(row, user, "reviewed", details)
    db.session.add(
        MaterialReviewCommand(
            record_id=row.id,
            idempotency_key=idempotency_key,
            request_digest=digest,
            result={"status": target_status, "version": row.version, "scoring": scoring_result},
            created_by=user.id,
        )
    )
    db.session.flush()
    return row, False

