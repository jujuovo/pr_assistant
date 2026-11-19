"""Student-confirmed OCR-to-material association; original OCR facts stay immutable."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import uuid

from flask import abort
from extensions import db
from material_models import MaterialAttachment, MaterialRecord
from models import Application
from ocr_models import OCRJob, OCRMaterialLink
from services.automation import actor
from services.materials.schemas import normalize, analyze, object_keys, integer
from services.materials.service import make_record, record_at, version_change, event, stored_path
from .jobs import authorized_job, job_root
from .mapping import suggestions
from .service import MAX_BYTES


def _draft_application(application_id, student_id, faculty_id):
    if application_id is None:
        return
    integer(application_id, "application_id", 1, 2_000_000_000)
    row = Application.query.filter_by(id=application_id).with_for_update().first_or_404()
    if row.student_id != student_id or row.faculty_id != faculty_id:
        abort(403, description="不能关联其他学生或学院的申请")
    if row.status != "draft":
        abort(409, description="仅可关联草稿申请")


def _material(job, mapped, payload, user):
    object_keys(payload, {"year", "data", "application_id", "material_record_id", "version"})
    target = mapped["material_category"]
    if payload.get("material_record_id") is None:
        object_keys(payload, {"year", "data", "application_id"}, {"year", "data"})
        _draft_application(payload.get("application_id"), user.student_id, user.faculty_id)
        return make_record(target, payload)
    object_keys(payload, {"material_record_id", "version", "data", "application_id"},
                {"material_record_id", "version", "data"})
    row = record_at(target, integer(payload["material_record_id"], "material_record_id", 1, 2_000_000_000))
    if row.student_id != user.student_id or row.faculty_id != job.faculty_id:
        abort(403)
    application_id = payload.get("application_id", row.application_id)
    _draft_application(application_id, user.student_id, row.faculty_id)
    data = normalize(target, payload["data"])
    version_change(row, payload["version"], ["draft", "needs_correction"],
                   {"data": data, "analysis": analyze(target, data), "check_report": None,
                    "status": "draft", "application_id": application_id})
    return row


def _original(job):
    path = job_root(job.id) / ("input" + Path(job.filename).suffix.lower())
    try:
        with path.open("rb") as source:
            payload = source.read(MAX_BYTES + 1)
        if not 0 < len(payload) <= MAX_BYTES or sha256(payload).hexdigest() != job.sha256:
            raise ValueError()
    except (OSError, ValueError):
        abort(409, description="OCR原件缺失或发生变化，请重新上传")
    return payload


def _existing_original(row, job):
    item = next((item for item in row.attachments if item.sha256 == job.sha256), None)
    if item is None:
        return False
    try:
        with stored_path(item.stored_name).open("rb") as source:
            data = source.read(MAX_BYTES + 1)
        if len(data) != item.size or sha256(data).hexdigest() != job.sha256:
            raise ValueError()
    except (OSError, ValueError):
        abort(409, description="已有材料原件发生变化，请先核对并重新上传")
    return True


def confirm(job_id, payload):
    user = actor()
    job = authorized_job(job_id)
    if user.role != "student" or job.user_id != user.id or job.faculty_id != user.faculty_id:
        abort(403, description="仅原上传学生可确认识别结果")
    job = OCRJob.query.filter_by(id=job.id).with_for_update().populate_existing().one()
    if db.session.get(OCRMaterialLink, job.id):
        abort(409, description="该识别任务已关联材料，请编辑原材料记录")
    if job.status not in ("extracted", "manual_review") or not job.report:
        abort(409, description="识别未完成或失败，不能确认")
    mapped = suggestions(job.category, job.report)
    if not mapped or not mapped["material_category"]:
        abort(409, description="尚未识别出可关联的材料类型")
    data = _original(job)
    created = None
    try:
        row = _material(job, mapped, payload, user)
        if not _existing_original(row, job):
            if len(row.attachments) >= 10:
                abort(409, description="材料附件已满")
            stored = uuid.uuid4().hex + Path(job.filename).suffix.lower()
            created = stored_path(stored)
            created.parent.mkdir(parents=True, exist_ok=True)
            with created.open("xb") as output:
                output.write(data)
            db.session.add(MaterialAttachment(record_id=row.id, filename=job.filename,
                stored_name=stored, sha256=job.sha256, size=len(data)))
        db.session.add(OCRMaterialLink(job_id=job.id, material_record_id=row.id,
            suggestions=deepcopy(mapped), confirmed_snapshot=deepcopy(row.data), actor_id=user.id))
        event(row, "ocr_confirmed", {"job_id": job.id, "source_sha256": job.sha256,
              "version": row.version, "suggestions": mapped, "confirmed_data": row.data})
        db.session.commit()
        db.session.expire(row, ["attachments"])
        return row
    except Exception:
        db.session.rollback()
        if created is not None:
            created.unlink(missing_ok=True)
        raise


def record_links(record):
    return [{"job_id": link.job_id, "category": link.job.category,
             "suggestions": link.suggestions, "confirmed_snapshot": link.confirmed_snapshot,
             "result_url": f"/api/ocr/jobs/{link.job_id}",
             "artifact_urls": {name: f"/api/ocr/jobs/{link.job_id}/images/{name}"
                               for name in (link.job.report or {}).get("images", {})}}
            for link in OCRMaterialLink.query.filter_by(material_record_id=record.id).order_by(OCRMaterialLink.created_at, OCRMaterialLink.job_id).all()]
