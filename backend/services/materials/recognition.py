"""Queue OCR from an existing material attachment with ownership and version checks."""
from hashlib import sha256

from flask import abort
from services.automation import actor
from .schemas import integer, object_keys
from .service import record_at, stored_path
from services.competition_ocr.jobs import enqueue
from services.competition_ocr.mapping import TARGETS
from services.competition_ocr.service import MAX_BYTES


def recognize_attachment(category, record_id, payload):
    row = record_at(category, record_id)
    user = actor()
    if user.role != "student" or row.student_id != user.student_id:
        abort(403)
    object_keys(payload, {"version", "attachment_id", "project_key"}, {"version", "attachment_id", "project_key"})
    if integer(payload["version"], "version", 1, 2_000_000_000) != row.version or row.status not in ("draft", "needs_correction"):
        abort(409, description="材料已提交或版本变化")
    key = payload["project_key"]
    if not isinstance(key, str) or category not in TARGETS.get(key, []):
        raise ValueError("识别项目与材料类别不匹配")
    attachment_id = integer(payload["attachment_id"], "attachment_id", 1, 2_000_000_000)
    attachment = next((item for item in row.attachments if item.id == attachment_id), None)
    if attachment is None:
        abort(404)
    try:
        with stored_path(attachment.stored_name).open("rb") as source:
            content = source.read(MAX_BYTES + 1)
    except OSError:
        abort(409, description="原件缺失")
    if len(content) != attachment.size or sha256(content).hexdigest() != attachment.sha256:
        abort(409, description="原件校验失败")
    if category == "competition":
        from extensions import db
        from ocr_models import OCRJob
        from services.competition_ocr.bridge import queue_material
        job, _ = queue_material(row, payload["version"], attachment_id=attachment_id, expected_key=key)
        return db.session.get(OCRJob, job.job_id)
    return enqueue(key, content, attachment.filename)
