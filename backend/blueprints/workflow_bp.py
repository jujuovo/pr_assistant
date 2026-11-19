"""HTTP adapters for auditable score and ranking workflow use cases."""

from datetime import datetime, timedelta

from flask import Blueprint, abort, jsonify, request

from models import Student
from services.automation import actor
from services.materials.schemas import integer
from use_cases.scoring import (
    ScoringUseCaseError,
    execute_score_recalculation,
    explain_student_score,
    recalculate_score_snapshots,
)
from use_cases.ranking import (
    RankingUseCaseError, execute_ranking_command, generate_ranking_command,
)
from use_cases.cycles import CycleUseCaseError, current_cycle_policy
from workflow_models import (RankingBatch, RankingEntry, RankingExportAudit,
                             StudentScoreSnapshot)
from extensions import db
from services.workflow_schemas import (
    cycle_policy_dto, ranking_batch_dto, ranking_presentation_dto, score_snapshot_dto,
)


workflow_bp = Blueprint("workflow", __name__, url_prefix="/api/workflow")


@workflow_bp.errorhandler(ScoringUseCaseError)
def scoring_error(error):
    return jsonify({"error": str(error), "code": error.code}), error.status_code


@workflow_bp.errorhandler(RankingUseCaseError)
def ranking_error(error):
    status = 403 if error.code == "forbidden" else 404 if error.code == "not_found" else 409
    return jsonify({"error":str(error),"code":error.code,
                    "blockers": getattr(error, "details", [])}), status


@workflow_bp.errorhandler(CycleUseCaseError)
def cycle_error(error):
    status = 403 if error.code == "forbidden" else 409
    return jsonify({"error": str(error), "code": error.code}), status


@workflow_bp.get("/cycles/current")
def current_cycle():
    actor()
    return jsonify(cycle_policy_dto(current_cycle_policy()))


def _authorize_student_score(user, student):
    if user.role == "student" and user.student_id == student.student_id:
        return
    if user.role in {"teacher", "admin"} and user.faculty_id == student.faculty_id:
        return
    abort(403, description="没有该学生成绩权限")


def _student_score_response(user, student, year):
    _authorize_student_score(user, student)
    return jsonify(score_snapshot_dto(explain_student_score(student.student_id, year)))


@workflow_bp.get("/students/<student_id>/score/current")
def current_student_score(student_id):
    user = actor()
    student = Student.query.filter_by(student_id=student_id).first_or_404()
    policy = current_cycle_policy()
    return _student_score_response(user, student, policy.cycle_code)


@workflow_bp.get("/students/<student_id>/score")
def student_score(student_id):
    user = actor()
    student = Student.query.filter_by(student_id=student_id).first_or_404()
    year = integer(int(request.args.get("year", "0")), "year", 2000, 2100)
    return _student_score_response(user, student, year)


@workflow_bp.post("/scores/recalculate")
def recalculate_scores():
    user = actor()
    if user.role != "admin" or not user.faculty_id:
        abort(403, description="仅管理员可预览或重算成绩")
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400, description="请求体必须为JSON对象")
    year = integer(payload.get("year"), "year", 2000, 2100)
    faculty_id = payload.get("faculty_id", user.faculty_id)
    if faculty_id != user.faculty_id:
        abort(403, description="不能重算其他学院")
    result = recalculate_score_snapshots(
        year,
        student_id=payload.get("student_id"),
        faculty_id=faculty_id,
        major_id=payload.get("major_id"),
        rule_version_id=payload.get("rule_version_id"),
        preview=payload.get("preview", False) is True,
    )
    return jsonify(result), 200 if result["complete"] else 409


@workflow_bp.post("/scores/recalculation-previews")
def preview_score_recalculation():
    """Return a read-only, scope-bound impact preview for an administrator."""
    user = actor()
    if user.role != "admin" or not user.faculty_id:
        abort(403, description="仅管理员可预览成绩重算")
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400, description="请求体必须为JSON对象")
    year = integer(payload.get("year"), "year", 2000, 2100)
    faculty_id = payload.get("faculty_id", user.faculty_id)
    if faculty_id != user.faculty_id:
        abort(403, description="不能预览其他学院的重算")
    major_id = payload.get("major_id")
    if major_id is not None:
        major_id = integer(major_id, "major_id", 1, 2147483647)
        if not Student.query.filter_by(
            faculty_id=faculty_id, major_id=major_id
        ).first():
            abort(403, description="专业不在管理员授权范围")
    result = recalculate_score_snapshots(
        year,
        student_id=payload.get("student_id"),
        faculty_id=faculty_id,
        major_id=major_id,
        rule_version_id=payload.get("rule_version_id"),
        preview=True,
    )
    result["preview_expires_at"] = (
        datetime.utcnow().replace(microsecond=0) + timedelta(minutes=15)
    ).isoformat() + "Z"
    return jsonify(result), 200 if result["complete"] else 409


@workflow_bp.post("/scores/recalculation-executions")
def execute_score_recalculation_endpoint():
    user = actor()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400, description="请求体必须为JSON对象")
    result = execute_score_recalculation(
        user, scope=payload.get("scope"), preview_digest=payload.get("preview_digest"),
        preview_expires_at=payload.get("preview_expires_at"),
        idempotency_key=payload.get("idempotency_key"))
    db.session.commit()
    return jsonify(result), 200 if result["complete"] else 409


def _ranking_actions(role, status):
    if role == "student":
        return ["view"]
    if role == "teacher":
        return ["view", "export"]
    actions = ["view", "export"]
    actions += {"draft": ["freeze"], "frozen": ["request_correction", "publish"],
                "published": ["withdraw"], "withdrawn": ["create_successor"]}.get(status, [])
    return actions


def _ranking_view(user, batch, entries):
    source = {
        "id": batch.id, "faculty_id": batch.faculty_id, "version": batch.version,
        "status": batch.status, "scope_definition": batch.scope_definition,
        "stale_reason": batch.stale_reason or batch.correction_reason,
        "created_at": batch.created_at, "updated_at": batch.updated_at,
        "published_at": batch.published_at,
        "total_count": db.session.query(RankingEntry).filter_by(batch_id=batch.id).count(),
        "allowed_actions": _ranking_actions(user.role, batch.status),
    }
    snapshots = {item.id: item for item in StudentScoreSnapshot.query.filter(
        StudentScoreSnapshot.id.in_([row.score_snapshot_id for row in entries
                                     if row.score_snapshot_id is not None])
    ).all()} if entries and user.role in {"teacher", "admin"} else {}
    presented_entries = [{
        "student_id": row.student_id, "frozen_score": row.frozen_score,
        "rank": row.rank, "eligible": row.eligible,
        "exclusion_reason": row.exclusion_reason,
        "score_basis": (snapshots[row.score_snapshot_id].breakdown
                        if row.score_snapshot_id in snapshots else []),
    } for row in entries]
    return ranking_presentation_dto(
        source, presented_entries, role=user.role, student_id=user.student_id,
        faculty_id=user.faculty_id,
    )


@workflow_bp.get("/rankings/<int:batch_id>")
def ranking_detail(batch_id):
    user=actor(); batch=db.get_or_404(RankingBatch,batch_id)
    if user.role=="student":
        entries=RankingEntry.query.filter_by(batch_id=batch.id,student_id=user.student_id).all()
    elif user.role in {"teacher","admin"} and user.faculty_id==batch.faculty_id:
        entries=RankingEntry.query.filter_by(batch_id=batch.id).order_by(RankingEntry.display_order).all()
    else:
        abort(403,description="没有该排名范围权限")
    return jsonify(_ranking_view(user,batch,entries))


@workflow_bp.post("/rankings/generate")
def generate_ranking():
    user = actor(); payload = request.get_json(silent=True) or {}
    try:
        cutoff = datetime.fromisoformat(payload.get("cutoff_at", ""))
    except (TypeError, ValueError):
        abort(400, description="cutoff_at 必须是 ISO 时间")
    batch, _ = generate_ranking_command(
        user, year=integer(payload.get("year"), "year", 2000, 2100),
        faculty_id=payload.get("faculty_id", user.faculty_id),
        major_id=payload.get("major_id"), cutoff_at=cutoff,
        precision=payload.get("precision", 4),
        idempotency_key=payload.get("idempotency_key"),
    )
    db.session.commit()
    entries = RankingEntry.query.filter_by(batch_id=batch.id).order_by(RankingEntry.display_order).all()
    return jsonify(_ranking_view(user, batch, entries)), 201


@workflow_bp.post("/rankings/<int:batch_id>/commands/<action>")
def ranking_command(batch_id, action):
    user = actor(); payload = request.get_json(silent=True) or {}
    extra = {}
    if "reason" in payload:
        extra["reason"] = payload["reason"]
    batch, _ = execute_ranking_command(
        user, batch_id, action=action, version=payload.get("version"),
        idempotency_key=payload.get("idempotency_key"), payload=extra,
    )
    db.session.commit()
    entries = RankingEntry.query.filter_by(batch_id=batch.id).order_by(RankingEntry.display_order).all()
    return jsonify(_ranking_view(user, batch, entries))


@workflow_bp.post("/rankings/<int:batch_id>/export")
def export_ranking(batch_id):
    user=actor(); batch=db.get_or_404(RankingBatch,batch_id)
    if user.role not in {"teacher","admin"} or user.faculty_id!=batch.faculty_id:
        abort(403,description="没有该排名导出权限")
    payload=request.get_json(silent=True) or {}; purpose=payload.get("purpose","")
    if not isinstance(purpose,str) or not purpose.strip() or len(purpose)>500:
        abort(400,description="导出用途必须为1至500字符")
    entries=RankingEntry.query.filter_by(batch_id=batch.id).order_by(RankingEntry.display_order).all()
    db.session.add(RankingExportAudit(batch_id=batch.id,actor_id=user.id,
                                      entry_count=len(entries),purpose=purpose.strip()))
    db.session.commit()
    return jsonify(_ranking_view(user,batch,entries))
