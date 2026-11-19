"""Private storage and session-based access for OCR jobs."""
from hashlib import sha256
from pathlib import Path
import uuid

from flask import abort, current_app
from extensions import db
from ocr_models import OCRJob
from services.automation import actor
from services.certificates.service import contained
from .catalog import category, IMAGE_EXTENSIONS
from .service import MAX_BYTES, _decode


def job_root(job_id):
    root = Path(current_app.config.get("OCR_STORAGE_FOLDER", Path(current_app.instance_path) / "ocr-jobs")).resolve()
    return contained(root, job_id)


def authorized_job(job_id):
    user = actor()
    row = db.get_or_404(OCRJob, job_id)
    if row.user_id != user.id and not (
        user.role in ("teacher", "admin") and user.faculty_id == row.faculty_id
    ):
        abort(403, description="没有该 OCR 材料的访问权限")
    return row


def job_view(row):
    from ocr_models import OCRMaterialLink
    from material_models import MaterialRecord
    from .mapping import suggestions
    link = db.session.get(OCRMaterialLink, row.id)
    material = db.session.get(MaterialRecord, link.material_record_id) if link else None
    return {"id": row.id, "category": row.category, "status": row.status, "report": row.report,
            "error": row.error, "authenticity": "not_assessed",
            "mapping": suggestions(row.category, row.report),
            "material_record_id": material.id if material else None,
            "material_url": f"/api/materials/{material.category}/records/{material.id}" if material else None,
            "application_id": material.application_id if material else None,
            "result_url": f"/api/ocr/jobs/{row.id}",
            "artifact_urls": {key: f"/api/ocr/jobs/{row.id}/images/{key}"
                              for key in (row.report or {}).get("images", {})}}


def enqueue(key, payload, filename):
    user = actor()
    category(key)
    if user.role not in ("student", "teacher", "admin") or not user.faculty_id:
        abort(403, description="请完善学院资料")
    if OCRJob.query.filter_by(user_id=user.id).filter(OCRJob.status.in_(("queued", "processing"))).count() >= 10:
        abort(429, description="待处理材料较多，请等待已有任务完成")
    _decode(payload).close()
    name = (filename or "upload.png").replace("\\", "/").split("/")[-1]
    if Path(name).suffix.lower() not in IMAGE_EXTENSIONS or len(name) > 255:
        raise ValueError("请输入有效的图片文件名")
    row = OCRJob(id=str(uuid.uuid4()), user_id=user.id, faculty_id=user.faculty_id, category=key,
                 filename=name, sha256=sha256(payload).hexdigest())
    folder = job_root(row.id)
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / ("input" + Path(name).suffix.lower())
    try:
        path.write_bytes(payload)
        db.session.add(row)
        db.session.commit()
    except Exception:
        db.session.rollback()
        path.unlink(missing_ok=True)
        folder.rmdir()
        raise
    return row
