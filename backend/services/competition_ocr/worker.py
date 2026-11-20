"""Lease and fencing checks keep expired OCR workers from replacing current results."""
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import uuid

from sqlalchemy import and_, or_
from automation_models import utcnow
from extensions import db
from ocr_models import OCRJob
from .jobs import job_root
from .service import CompetitionOCR, MAX_BYTES


def run_one_ocr(app, provider):
    eligible = or_(OCRJob.status == "queued", and_(
        OCRJob.status == "processing", OCRJob.lease_until < utcnow()))
    row = OCRJob.query.filter(eligible).order_by(OCRJob.created_at, OCRJob.id).first()
    if not row:
        return False
    token = str(uuid.uuid4())
    seconds = app.config.get("AUTOMATION_LEASE_SECONDS", 600)
    claimed = OCRJob.query.filter(OCRJob.id == row.id, eligible).update({
        "status": "processing", "lease_token": token, "lease_until": utcnow() + timedelta(seconds=seconds),
        "attempts": OCRJob.attempts + 1}, synchronize_session=False)
    db.session.commit()
    if not claimed:
        return True
    db.session.refresh(row)
    job_id, key, expected, attempts = row.id, row.category, row.sha256, row.attempts
    folder = job_root(job_id)
    original = folder / ("input" + Path(row.filename).suffix.lower())
    db.session.rollback()
    try:
        if attempts > app.config.get("AUTOMATION_MAX_ATTEMPTS", 3):
            raise ValueError("任务多次超时，请重新上传或人工核验")
        with original.open("rb") as source:
            payload = source.read(MAX_BYTES + 1)
        if sha256(payload).hexdigest() != expected:
            raise ValueError("原件摘要不一致，请重新上传")
        if not 0 < len(payload) <= MAX_BYTES:
            raise ValueError("原件大小异常，请重新上传")
        if key == "volunteer":
            from services.recognition.volunteer_material import recognize
            report = recognize(provider, original)
        else:
            report = CompetitionOCR(provider).recognize(original, key, image_dir=folder / token)
        if report["source_sha256"] != expected:
            raise ValueError("识别期间原件内容发生变化")
        report["images"] = {name: f"{token}/{filename}" for name, filename in report["images"].items()}
        status, error = report["status"], None
    except Exception:
        app.logger.exception("分类 OCR 任务失败：%s", job_id)
        report, status, error = None, "failed", "识别失败，请检查原件、模型或重新上传材料"
    published = OCRJob.query.filter_by(id=job_id, lease_token=token, status="processing").update({
        "report": report, "status": status, "error": error,
        "lease_token": None, "lease_until": None}, synchronize_session=False)
    if published:
        if key == "volunteer":
            from services.volunteer_ocr import publish
            job = OCRJob.query.filter_by(id=job_id).populate_existing().one()
            publish(job)
        else:
            from .bridge import publish_material_result
            publish_material_result(job_id, report, error)
    db.session.commit()
    return True
