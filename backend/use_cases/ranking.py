"""Ranking batch application use cases."""

import hashlib
import json
from automation_models import utcnow

from domain.ranking import candidate, competition_ranking
from extensions import db
from models import Student
from workflow_models import (
    RankingBatch, RankingCommand, RankingEntry, RankingStateEvent, StudentScoreSnapshot,
)


class RankingUseCaseError(ValueError):
    def __init__(self, message, *, code="invalid_ranking_state", details=None):
        super().__init__(message)
        self.code = code
        self.details = list(details or [])


def _ranking_request_digest(action, payload):
    encoded = json.dumps({"action": action, "payload": payload}, sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_idempotency_key(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise RankingUseCaseError("幂等键必须为1至128字符", code="invalid_command")


def _replay_ranking_command(action, key, payload):
    _validate_idempotency_key(key)
    digest = _ranking_request_digest(action, payload)
    previous = RankingCommand.query.filter_by(idempotency_key=key).one_or_none()
    if previous and (previous.action != action or previous.request_digest != digest):
        raise RankingUseCaseError("幂等键已用于不同排名命令", code="idempotency_conflict")
    return previous, digest


def _record_ranking_command(user, action, key, digest, batch):
    result = {"batch_id": batch.id, "status": batch.status, "version": batch.version}
    db.session.add(RankingCommand(
        idempotency_key=key, action=action, request_digest=digest,
        batch_id=batch.id, result=result, created_by=user.id, created_at=utcnow(),
    ))
    db.session.flush()
    return result


def generate_ranking_command(
    user, *, year, faculty_id, major_id, cutoff_at, precision,
    idempotency_key, fail_at=None,
):
    if user.role != "admin" or user.faculty_id != faculty_id:
        raise RankingUseCaseError("仅本学院管理员可生成排名", code="forbidden")
    payload = {"year": year, "faculty_id": faculty_id, "major_id": major_id,
               "cutoff_at": cutoff_at.isoformat(), "precision": precision}
    previous, digest = _replay_ranking_command("generate", idempotency_key, payload)
    if previous:
        return db.session.get(RankingBatch, previous.batch_id), False
    batch, created = generate_ranking_draft(
        year, faculty_id, major_id=major_id, cutoff_at=cutoff_at,
        created_by=user.id, precision=precision,
    )
    if fail_at == "after_action":
        raise RuntimeError("injected ranking command failure")
    _record_ranking_command(user, "generate", idempotency_key, digest, batch)
    return batch, created


def execute_ranking_command(
    user, batch_id, *, action, version, idempotency_key, payload=None, fail_at=None
):
    payload = dict(payload or {})
    request_value = {"batch_id": batch_id, "version": version, **payload}
    previous, digest = _replay_ranking_command(action, idempotency_key, request_value)
    if previous:
        return db.session.get(RankingBatch, previous.batch_id), False
    batch = RankingBatch.query.filter_by(id=batch_id).with_for_update().one_or_none()
    if batch is None:
        raise RankingUseCaseError("排名批次不存在", code="not_found")
    if action == "freeze":
        result = freeze_ranking_batch(user, batch, version)
    elif action == "request_correction":
        result = request_ranking_correction(user, batch, version, payload.get("reason"))
    elif action == "publish":
        result = publish_ranking_batch(user, batch, version)
    elif action == "withdraw":
        result = withdraw_ranking_batch(user, batch, version, payload.get("reason"))
    elif action == "create_successor":
        if batch.version != version:
            raise RankingUseCaseError("排名批次版本已变化", code="version_conflict")
        cutoff = payload.get("cutoff_at")
        result = create_successor_draft(user, batch, cutoff_at=cutoff)
    else:
        raise RankingUseCaseError("未知排名命令", code="invalid_command")
    if fail_at == "after_action":
        raise RuntimeError("injected ranking command failure")
    _record_ranking_command(user, action, idempotency_key, digest, result)
    return result, True


def select_ranking_candidates(year, faculty_id, *, major_id=None, cutoff_at=None):
    query = Student.query.filter_by(faculty_id=faculty_id).order_by(Student.student_id)
    if major_id is not None:
        query = query.filter_by(major_id=major_id)
    result = []
    for student in query.all():
        snapshots = StudentScoreSnapshot.query.filter_by(
            student_id=student.student_id, year=year, status="current"
        )
        if cutoff_at is not None:
            snapshots = snapshots.filter(StudentScoreSnapshot.updated_at <= cutoff_at)
        snapshot = snapshots.order_by(StudentScoreSnapshot.version.desc()).first()
        result.append(
            candidate(
                student.student_id,
                student.academic_score,
                snapshot.id if snapshot else None,
                snapshot.comprehensive_score if snapshot else None,
            )
        )
    return tuple(result)


def generate_ranking_draft(
    year,
    faculty_id,
    *,
    major_id,
    cutoff_at,
    created_by,
    precision=4,
):
    candidates = select_ranking_candidates(
        year, faculty_id, major_id=major_id, cutoff_at=cutoff_at
    )
    placements = competition_ranking(candidates, precision=precision)
    scope = {"faculty_id": faculty_id, "major_id": major_id, "year": year}
    digest_payload = {
        "scope": scope,
        "cutoff_at": cutoff_at.isoformat(),
        "precision": precision,
        "entries": [
            {
                "student_id": item.student_id,
                "snapshot_id": item.snapshot_id,
                "score": str(item.score) if item.score is not None else None,
                "eligible": item.eligible,
                "reason": item.exclusion_reason,
            }
            for item in placements
        ],
    }
    input_digest = hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    existing = RankingBatch.query.filter_by(
        year=year,
        faculty_id=faculty_id,
        scope_type="major",
        input_digest=input_digest,
    ).first()
    if existing:
        return existing, False
    snapshot_ids = [item.snapshot_id for item in placements if item.snapshot_id]
    snapshots = StudentScoreSnapshot.query.filter(
        StudentScoreSnapshot.id.in_(snapshot_ids)
    ).all() if snapshot_ids else []
    rule_version_ids = sorted(
        {rule_id for snapshot in snapshots for rule_id in snapshot.rule_version_ids}
    )
    batch = RankingBatch(
        year=year,
        faculty_id=faculty_id,
        major_id=major_id,
        scope_type="major",
        scope_definition=scope,
        cutoff_at=cutoff_at,
        rule_version_ids=rule_version_ids,
        score_precision=precision,
        status="draft",
        version=1,
        input_digest=input_digest,
        created_by=created_by,
    )
    db.session.add(batch)
    db.session.flush()
    for item in placements:
        db.session.add(
            RankingEntry(
                batch_id=batch.id,
                student_id=item.student_id,
                score_snapshot_id=item.snapshot_id,
                frozen_score=item.score,
                rank=item.rank,
                display_order=item.display_order,
                eligible=item.eligible,
                exclusion_reason=item.exclusion_reason,
            )
        )
    db.session.flush()
    return batch, True


def _authorize_admin(user, batch):
    if user.role != "admin" or user.faculty_id != batch.faculty_id:
        raise RankingUseCaseError("仅本学院管理员可操作排名批次", code="forbidden")


def ranking_freeze_blockers(batch, *, unresolved_differences=0):
    blockers = []
    if batch.status == "stale":
        blockers.append({"type": "stale_input", "batch_id": batch.id,
                         "reason": batch.stale_reason or "ranking_inputs_changed"})
        return blockers
    entries = RankingEntry.query.filter_by(batch_id=batch.id).order_by(
        RankingEntry.display_order
    ).all()
    for entry in entries:
        if not entry.eligible:
            blockers.append({"type": "eligibility", "student_id": entry.student_id,
                             "reason": entry.exclusion_reason or "student_not_eligible"})
        if entry.score_snapshot_id is None:
            blockers.append({"type": "snapshot", "student_id": entry.student_id,
                             "reason": "missing_score_snapshot"})
            continue
        snapshot = db.session.get(StudentScoreSnapshot, entry.score_snapshot_id)
        if snapshot is None:
            blockers.append({"type": "snapshot", "student_id": entry.student_id,
                             "reason": "score_snapshot_not_found"})
            continue
        latest = StudentScoreSnapshot.query.filter_by(
            student_id=entry.student_id, year=batch.year, status="current"
        ).order_by(StudentScoreSnapshot.version.desc()).first()
        if latest is None or latest.id != snapshot.id:
            blockers.append({"type": "stale_input", "student_id": entry.student_id,
                             "reason": "score_snapshot_changed",
                             "expected_snapshot_id": entry.score_snapshot_id,
                             "current_snapshot_id": latest.id if latest else None})
        missing_rules = sorted(set(snapshot.rule_version_ids or []) - set(batch.rule_version_ids or []))
        if missing_rules:
            blockers.append({"type": "rule_version", "student_id": entry.student_id,
                             "reason": "rule_version_not_bound", "rule_version_ids": missing_rules})
    from use_cases.migration import legacy_reconciliation_report
    reconciliation = legacy_reconciliation_report(batch.year, faculty_id=batch.faculty_id)
    if unresolved_differences or reconciliation["release_blocks"]:
        blockers.append({"type": "reconciliation", "reason": "unresolved_legacy_differences",
                         "count": unresolved_differences + len(reconciliation["release_blocks"]),
                         "items": reconciliation["release_blocks"]})
    return blockers


def freeze_ranking_batch(user, batch, version, *, unresolved_differences=0):
    _authorize_admin(user, batch)
    if batch.version != version:
        raise RankingUseCaseError("排名批次状态或版本已变化", code="version_conflict")
    if batch.status not in {"draft", "stale"}:
        raise RankingUseCaseError("仅草稿可冻结", code="invalid_ranking_state")
    blockers = ranking_freeze_blockers(batch, unresolved_differences=unresolved_differences)
    if blockers:
        types = {item["type"] for item in blockers}
        code = ("reconciliation_blocked" if types == {"reconciliation"}
                else "eligibility_blocked" if types == {"eligibility", "snapshot"}
                else "freeze_blocked")
        raise RankingUseCaseError("排名冻结校验未通过", code=code, details=blockers)
    batch.status = "frozen"
    batch.version += 1
    batch.frozen_by = user.id
    batch.frozen_at = utcnow()
    batch.updated_at = utcnow()
    return batch


def publish_ranking_batch(user, batch, version):
    _authorize_admin(user, batch)
    if batch.version != version or batch.status != "frozen":
        raise RankingUseCaseError("仅可发布当前冻结版本", code="version_conflict")
    batch.status = "published"
    batch.version += 1
    batch.published_by = user.id
    batch.published_at = utcnow()
    batch.updated_at = utcnow()
    return batch


def request_ranking_correction(user, batch, version, reason):
    _authorize_admin(user, batch)
    if batch.version != version:
        raise RankingUseCaseError("排名批次版本已变化", code="version_conflict")
    if batch.status == "published":
        raise RankingUseCaseError(
            "已发布排名不能解冻覆盖；请撤回并创建后继版本", code="published_immutable"
        )
    if batch.status != "frozen":
        raise RankingUseCaseError("仅未发布冻结批次可进入纠错", code="invalid_ranking_state")
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 1000:
        raise RankingUseCaseError("纠错理由必须为1至1000字符", code="invalid_reason")
    previous = batch.status
    batch.status = "correction_required"
    batch.version += 1
    batch.correction_reason = reason.strip()
    batch.correction_requested_by = user.id
    batch.correction_requested_at = batch.updated_at = utcnow()
    db.session.add(RankingStateEvent(
        batch_id=batch.id, from_status=previous, to_status=batch.status,
        reason=batch.correction_reason, batch_version=batch.version,
        actor_id=user.id, created_at=batch.updated_at,
    ))
    return batch


def withdraw_ranking_batch(user, batch, version, reason):
    _authorize_admin(user, batch)
    if batch.version != version or batch.status != "published":
        raise RankingUseCaseError("仅可撤回当前已发布版本", code="version_conflict")
    if not isinstance(reason, str) or not reason.strip():
        raise RankingUseCaseError("撤回理由不能为空")
    batch.status = "withdrawn"
    batch.version += 1
    batch.withdrawn_by = user.id
    batch.withdrawn_at = utcnow()
    batch.withdrawal_reason = reason.strip()
    batch.updated_at = utcnow()
    return batch


def create_successor_draft(user, withdrawn_batch, *, cutoff_at=None):
    _authorize_admin(user, withdrawn_batch)
    if withdrawn_batch.status != "withdrawn":
        raise RankingUseCaseError("仅撤回版本可创建后继排名")
    successor, created = generate_ranking_draft(
        withdrawn_batch.year,
        withdrawn_batch.faculty_id,
        major_id=withdrawn_batch.major_id,
        cutoff_at=cutoff_at or withdrawn_batch.cutoff_at,
        created_by=user.id,
        precision=withdrawn_batch.score_precision,
    )
    if not created or successor.id == withdrawn_batch.id:
        raise RankingUseCaseError("排名输入尚未变化，不能创建相同后继版本")
    successor.predecessor_batch_id = withdrawn_batch.id
    successor.source_summary = {
        "batch_id": withdrawn_batch.id, "status": withdrawn_batch.status,
        "version": withdrawn_batch.version, "input_digest": withdrawn_batch.input_digest,
    }
    successor.version = 1
    return successor


def create_corrected_draft(user, correction_batch, *, cutoff_at=None):
    _authorize_admin(user, correction_batch)
    if correction_batch.status != "correction_required":
        raise RankingUseCaseError("仅纠错状态可生成新草稿", code="invalid_ranking_state")
    successor, created = generate_ranking_draft(
        correction_batch.year, correction_batch.faculty_id,
        major_id=correction_batch.major_id,
        cutoff_at=cutoff_at or correction_batch.cutoff_at,
        created_by=user.id, precision=correction_batch.score_precision,
    )
    if not created or successor.id == correction_batch.id or successor.input_digest == correction_batch.input_digest:
        raise RankingUseCaseError(
            "权威来源尚未修正，不能从纠错批次生成相同排名", code="authoritative_source_unchanged"
        )
    successor.predecessor_batch_id = correction_batch.id
    successor.source_summary = {
        "batch_id": correction_batch.id, "status": correction_batch.status,
        "version": correction_batch.version, "input_digest": correction_batch.input_digest,
        "correction_reason": correction_batch.correction_reason,
    }
    return successor

