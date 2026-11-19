"""Cancelable, version-bound OCR assistance for competition materials."""

import uuid

from automation_models import utcnow
from extensions import db
from material_models import CompetitionOcrJob, MaterialEvent, MaterialRecord
from use_cases.materials import MaterialUseCaseError


def _require_owner(user, row):
    if user.role != "student" or user.student_id != row.student_id:
        raise MaterialUseCaseError("只能操作本人竞赛 OCR", code="forbidden", status_code=403)
    if row.category != "competition":
        raise MaterialUseCaseError("OCR 任务仅适用于竞赛材料", code="invalid_category")


def start_competition_ocr(user, row, version):
    _require_owner(user, row)
    if row.status != "draft" or row.version != version:
        raise MaterialUseCaseError("材料版本已变化", code="version_conflict", status_code=409)
    active = CompetitionOcrJob.query.filter_by(record_id=row.id, material_version=row.version).filter(
        CompetitionOcrJob.status.in_(("queued", "running"))
    ).first()
    if active is not None:
        return active, False
    job = CompetitionOcrJob(
        job_id=uuid.uuid4().hex,
        record_id=row.id,
        material_version=row.version,
        status="queued",
    )
    db.session.add(job)
    db.session.flush()
    db.session.add(MaterialEvent(
        record_id=row.id, actor_id=user.id, action="competition_ocr_started",
        details={"job_id": job.job_id, "material_version": row.version},
    ))
    return job, True


def cancel_competition_ocr(user, row, version, job_id):
    _require_owner(user, row)
    job = CompetitionOcrJob.query.filter_by(job_id=job_id, record_id=row.id).with_for_update().one_or_none()
    if job is None:
        raise MaterialUseCaseError("OCR 任务不存在", code="not_found", status_code=404)
    if row.status != "draft" or row.version != version:
        raise MaterialUseCaseError("材料版本已变化", code="version_conflict", status_code=409)
    if job.status in {"cancelled", "ignored"}:
        return job
    if job.status not in {"queued", "running"}:
        raise MaterialUseCaseError("OCR 任务已经结束", code="ocr_job_finished", status_code=409)
    changed = MaterialRecord.query.filter_by(id=row.id, version=version, status="draft").update(
        {"version": MaterialRecord.version + 1, "updated_at": utcnow()},
        synchronize_session=False,
    )
    if not changed:
        raise MaterialUseCaseError("材料版本已变化", code="version_conflict", status_code=409)
    job.cancelled = True
    job.status = "cancelled"
    job.updated_at = utcnow()
    db.session.add(MaterialEvent(
        record_id=row.id, actor_id=user.id, action="competition_ocr_cancelled",
        details={"job_id": job.job_id, "material_version": version},
    ))
    db.session.flush()
    db.session.refresh(row)
    return job


def complete_competition_ocr(job_id, result):
    """Worker completion: late/stale results are diagnostic-only."""
    job = CompetitionOcrJob.query.filter_by(job_id=job_id).with_for_update().one_or_none()
    if job is None:
        raise MaterialUseCaseError("OCR 任务不存在", code="not_found", status_code=404)
    row = db.session.get(MaterialRecord, job.record_id)
    if job.cancelled or job.status in {"cancelled", "ignored"} or row.version != job.material_version:
        job.status = "ignored"
        job.ignored_late_result = result
        job.updated_at = utcnow()
        return job, False
    if job.status not in {"queued", "running"}:
        return job, job.status == "completed"
    updated = MaterialRecord.query.filter_by(
        id=row.id, version=job.material_version, status="draft"
    ).update({"ocr_raw_terms": result, "updated_at": utcnow()}, synchronize_session=False)
    if not updated:
        job.status = "ignored"
        job.ignored_late_result = result
        job.updated_at = utcnow()
        return job, False
    job.status = "completed"
    job.raw_result = result
    job.updated_at = utcnow()
    db.session.expire(row, ["ocr_raw_terms"])
    return job, True


def fail_competition_ocr(job_id, message):
    job = CompetitionOcrJob.query.filter_by(job_id=job_id).with_for_update().one_or_none()
    if job is None:
        raise MaterialUseCaseError("OCR 任务不存在", code="not_found", status_code=404)
    if job.status in {"queued", "running"}:
        job.status = "failed"
        job.error = str(message)[:1000]
        job.updated_at = utcnow()
    return job
