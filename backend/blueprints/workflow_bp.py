"""HTTP adapters for auditable score and ranking workflow use cases."""

from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Blueprint, abort, jsonify, request

from models import Major, Student
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
from use_cases.cycles import (CycleUseCaseError, current_cycle_policy,
                             create_cycle_policy, activate_cycle_policy, switch_cycle_policy)
from workflow_models import (RecommendationCyclePolicy, RankingBatch, RankingEntry, RankingExportAudit,
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


def _admin_cycle(user):
    if user.role != "admin":
        raise CycleUseCaseError("仅管理员可管理推免周期", code="forbidden")


def _cycle_admin_dto(policy):
    return {"id": policy.id, **cycle_policy_dto(policy)}


@workflow_bp.get("/cycles")
def list_cycles():
    _admin_cycle(actor())
    policies = RecommendationCyclePolicy.query.order_by(
        RecommendationCyclePolicy.cycle_code.desc(), RecommendationCyclePolicy.version.desc()
    ).all()
    return jsonify({"items": [_cycle_admin_dto(item) for item in policies],
                    "active_id": next((item.id for item in policies if item.active_marker == 1), None)})


@workflow_bp.post("/cycles")
def create_cycle():
    user = actor()
    _admin_cycle(user)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400, description="请求体必须为 JSON 对象")
    try:
        start = date.fromisoformat(payload.get("eligible_award_start_date", ""))
        end = date.fromisoformat(payload.get("eligible_award_end_date", ""))
    except (TypeError, ValueError):
        abort(400, description="请填写有效的奖项起止日期")
    policy, created = create_cycle_policy(user, payload.get("cycle_code"), start, end,
                                           payload.get("display_name"))
    db.session.commit()
    return jsonify(_cycle_admin_dto(policy)), 201 if created else 200


@workflow_bp.post("/cycles/<int:policy_id>/activate")
def activate_cycle(policy_id):
    user = actor()
    _admin_cycle(user)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or "expected_active_id" not in payload:
        abort(400, description="请提供当前活动周期 ID（无活动周期时填 null）")
    policy = db.get_or_404(RecommendationCyclePolicy, policy_id)
    active = current_cycle_policy(required=False)
    expected = payload["expected_active_id"]
    if isinstance(expected, bool) or (expected is not None and not isinstance(expected, int)):
        abort(400, description="当前活动周期 ID 无效")
    if (active.id if active else None) != expected:
        raise CycleUseCaseError("活动周期已变化，请刷新后重试", code="version_conflict")
    if active:
        switch_cycle_policy(user, policy, expected_active_id=expected)
    else:
        activate_cycle_policy(user, policy)
    db.session.commit()
    return jsonify(_cycle_admin_dto(policy))


def _authorize_student_score(user, student):
    if user.role == "student" and user.student_id == student.student_id:
        return
    if user.role in {"teacher", "admin"} and user.faculty_id == student.faculty_id:
        return
    abort(403, description="没有该学生成绩权限")


def _student_score_response(user, student, year):
    _authorize_student_score(user, student)
    return jsonify(score_snapshot_dto(explain_student_score(student.student_id, year)))


@workflow_bp.get("/teacher/score-report")
def teacher_score_report():
    user = actor()
    if user.role != "teacher" or not user.faculty_id:
        abort(403, description="仅所属学院教师可查看报表")
    scope = {key: request.args.get(key, type=int) for key in ("faculty_id", "department_id", "major_id", "year")}
    if any(value is None or value <= 0 for value in scope.values()):
        abort(400, description="请选择学院、系、专业和推免周期")
    if scope["faculty_id"] != user.faculty_id:
        abort(403, description="无权查看其他学院报表")
    major = db.session.get(Major, scope["major_id"])
    if not major or major.department_id != scope["department_id"] or major.department.faculty_id != user.faculty_id:
        abort(404, description="所选系和专业不属于当前学院")
    year = scope.pop("year")
    if not RecommendationCyclePolicy.query.filter_by(cycle_code=year).first():
        return jsonify(error="该年份没有对应的推免周期，请选择有效周期。"), 400

    from material_models import MaterialRecord
    from workflow_models import ScoreEntry

    students = Student.query.filter_by(**scope).order_by(Student.student_id).all()
    snapshots = StudentScoreSnapshot.query.filter_by(
        faculty_id=user.faculty_id, year=year, status="current"
    ).filter(
        StudentScoreSnapshot.student_id.in_([student.student_id for student in students])
    ).order_by(StudentScoreSnapshot.version).all()
    by_student = {snapshot.student_id: snapshot for snapshot in snapshots}
    projects_by_student = {}
    entries = db.session.query(ScoreEntry, MaterialRecord).join(
        MaterialRecord, MaterialRecord.id == ScoreEntry.material_record_id
    ).filter(
        ScoreEntry.faculty_id == user.faculty_id, ScoreEntry.year == year,
        ScoreEntry.source_type == "material", ScoreEntry.status == "active",
        ScoreEntry.student_id.in_(list(by_student)),
        MaterialRecord.faculty_id == ScoreEntry.faculty_id,
        MaterialRecord.year == ScoreEntry.year,
        MaterialRecord.student_id == ScoreEntry.student_id,
    ).order_by(ScoreEntry.category, ScoreEntry.id)
    snapshot_scores = {
        student_id: {item["entry_id"]: item["effective_score"] for item in snapshot.breakdown
                     if "entry_id" in item}
        for student_id, snapshot in by_student.items()
    }
    for entry, material in entries:
        frozen_score = snapshot_scores[entry.student_id].get(entry.id)
        if frozen_score is None and entry.included:
            continue
        facts = {**(material.data or {}), **(material.confirmed_terms or {})}
        projects_by_student.setdefault(entry.student_id, []).append({
            "category": entry.category,
            "name": next((facts[key] for key in (
                "project_name", "paper_title", "patent_title", "title", "competition_name", "name"
            ) if isinstance(facts.get(key), str) and facts[key].strip()), None),
            "score": frozen_score if frozen_score is not None else "0",
            "exclusion_reason": entry.exclusion_reason,
        })
    report = []
    for student in students:
        snapshot = by_student.get(student.student_id)
        row = {
            "student_id": student.student_id, "name": student.student_name,
            "faculty": student.faculty.name, "department": major.department.name, "major": major.name,
            "gpa": student.gpa, "gender": student.gender,
            "cet4": student.cet4_score, "cet6": student.cet6_score,
            "projects": projects_by_student.get(student.student_id, []),
            "snapshot_status": snapshot.status if snapshot else "no_authoritative_snapshot",
        }
        for key, field in (
            ("academic_base", "academic_base_score"),
            ("academic_weight", "academic_weight"),
            ("academic_raw_total", "specialty_raw_score"),
            ("academic_total", "specialty_score"),
            ("comprehensive_raw_total", "performance_raw_score"),
            ("comprehensive_total", "performance_score"),
            ("score", "comprehensive_score"),
        ):
            row[key] = str(getattr(snapshot, field)) if snapshot else None
        report.append(row)
    scored = sorted((row for row in report if row["score"] is not None),
                    key=lambda row: Decimal(row["score"]), reverse=True)
    previous = None
    for position, row in enumerate(scored, start=1):
        score = Decimal(row["score"])
        if score != previous:
            rank = position
            previous = score
        row.update(report_rank=rank, ranked_count=len(scored))
    return jsonify(year=year, students=report)


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


@workflow_bp.get("/students/<student_id>/score-sources/<source_type>/<int:source_id>")
def score_source_route(student_id,source_type,source_id):
    user=actor()
    student=Student.query.filter_by(student_id=student_id).first_or_404()
    _authorize_student_score(user,student)
    try:
        year=integer(int(request.args.get("year","0")),"year",2000,2100)
    except (ValueError,TypeError):
        raise ScoringUseCaseError("请选择有效推免周期",status_code=400,code="invalid_cycle") from None
    from services.score_sources import score_source_detail
    return jsonify(score_source_detail(user,student,year,source_type,source_id))


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


@workflow_bp.get("/rankings")
def ranking_options():
    user = actor()
    query = db.session.query(RankingBatch, Major.name).outerjoin(Major, RankingBatch.major_id == Major.id)
    if user.role == "student" and user.student_id:
        query = query.filter(RankingEntry.query.filter(
            RankingEntry.batch_id == RankingBatch.id, RankingEntry.student_id == user.student_id
        ).exists())
    elif user.role in {"teacher", "admin"} and user.faculty_id:
        query = query.filter(RankingBatch.faculty_id == user.faculty_id)
    else:
        abort(403, description="没有排名查看权限")
    for param, column in (("major_id", RankingBatch.major_id), ("year", RankingBatch.year)):
        if param in request.args:
            value = request.args.get(param, type=int)
            if value is None or value <= 0:
                abort(400, description=f"{param} 必须为正整数")
            query = query.filter(column == value)
    rows = query.order_by(RankingBatch.created_at.desc(), RankingBatch.id.desc()).all()
    return jsonify(items=[{
        "batch_id": batch.id, "year": batch.year, "major_name": major_name,
        "version": batch.version, "status": batch.status,
    } for batch, major_name in rows])


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
