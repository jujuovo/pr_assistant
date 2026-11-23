"""Run the material OCR lifecycle through the local, leased recognition queue."""
from hashlib import sha256
from pathlib import Path
from flask import abort
from extensions import db
from material_models import CompetitionOcrJob, MaterialRecord
from ocr_models import OCRJob
from workflow_models import CompetitionRulePackage
from services.materials.service import stored_path
from .jobs import enqueue, job_root
from .catalog import IMAGE_EXTENSIONS
from .service import MAX_BYTES
from .workflow_mapping import FAMILIES
from .mapping import suggestions


def enqueue_material(row, job, *, attachment_id=None, expected_key=None):
    existing = db.session.get(OCRJob, job.job_id)
    package = db.session.get(CompetitionRulePackage, row.competition_rule_package_id)
    item = next((item for item in package.snapshot["catalog"]
                 if item["competition_id"] == row.data.get("competition_id")), None) if package else None
    key = next((key for key, family in FAMILIES.items() if item and item["event_family"] == family), None)
    if expected_key is not None and key != expected_key:
        raise ValueError("识别项目与正式竞赛条目不匹配")
    if not key:
        abort(409, description="该赛事暂无OCR适配器，请保留原件并人工填写")
    attachment = next((a for a in reversed(row.attachments)
                       if (attachment_id is None or a.id == attachment_id)
                       and Path(a.filename).suffix.lower() in IMAGE_EXTENSIONS), None)
    if not attachment:
        abort(400, description="请先上传一张清晰证书图片；PDF等材料可直接人工核验")
    try:
        with stored_path(attachment.stored_name).open("rb") as source:
            payload = source.read(MAX_BYTES + 1)
        if len(payload) != attachment.size or sha256(payload).hexdigest() != attachment.sha256:
            raise ValueError()
    except (OSError, ValueError):
        abort(409, description="原件缺失或校验失败，请重新上传")
    if existing:
        if existing.sha256 != sha256(payload).hexdigest():
            abort(409, description="已有任务使用其他原件，请先停止后重新识别")
        return None
    enqueue(key, payload, attachment.filename, job_id=job.job_id, commit=False)
    return job_root(job.job_id)


def publish_material_result(job_id, report, error=None):
    job = CompetitionOcrJob.query.filter_by(job_id=job_id).with_for_update().one_or_none()
    if job is None:
        return
    from use_cases.competition_ocr import complete_competition_ocr, fail_competition_ocr
    if error:
        fail_competition_ocr(job_id, error)
        return
    row = db.session.get(MaterialRecord, job.record_id)
    package = db.session.get(CompetitionRulePackage, row.competition_rule_package_id)
    result = {"report": report, "mapping": suggestions(report["category"], report, package),
              "artifact_urls": {name: f"/api/ocr/jobs/{job_id}/images/{name}" for name in report.get("images", {})}}
    complete_competition_ocr(job_id, result)


def queue_material(row, version, *, attachment_id=None, expected_key=None):
    from services.actors import actor
    from use_cases.competition_ocr import start_competition_ocr
    folder = None
    try:
        locked = MaterialRecord.query.filter_by(id=row.id).with_for_update().populate_existing().one()
        job, created = start_competition_ocr(actor(), locked, version)
        folder = enqueue_material(locked, job, attachment_id=attachment_id, expected_key=expected_key)
        db.session.commit()
        return job, created
    except Exception:
        db.session.rollback()
        if folder is not None:
            import shutil
            shutil.rmtree(folder)
        raise


def enqueue_created_material(user, row):
    """Called inside the single original+draft transaction, before committing."""
    from use_cases.competition_ocr import start_competition_ocr
    package = db.session.get(CompetitionRulePackage, row.competition_rule_package_id)
    item = next((i for i in package.snapshot["catalog"]
                 if i["competition_id"] == row.data.get("competition_id")), None)
    if not item or item["event_family"] not in FAMILIES.values():
        return None
    if not any(Path(a.filename).suffix.lower() in IMAGE_EXTENSIONS for a in row.attachments):
        return None
    job, _ = start_competition_ocr(user, row, row.version)
    try:
        enqueue_material(row, job)
    except Exception:
        import shutil
        shutil.rmtree(job_root(job.job_id),ignore_errors=True)
        raise
    return job
