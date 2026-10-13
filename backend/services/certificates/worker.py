"""数据库任务队列与租约隔离；识别结果不能修改申请分数或审核状态。"""
import uuid
from datetime import timedelta
from sqlalchemy import and_, or_
from extensions import db
from certificate_models import CertificateAssessment
from automation_models import utcnow
from .service import artifact_root, contained


def run_one_certificate(app, provider):
    now = utcnow()
    eligible = or_(CertificateAssessment.status == "queued", and_(
        CertificateAssessment.status == "processing", CertificateAssessment.lease_until < now))
    row = CertificateAssessment.query.filter(eligible).order_by(CertificateAssessment.id).first()
    if not row:
        return False
    token = str(uuid.uuid4())
    seconds = app.config.get("AUTOMATION_LEASE_SECONDS", 600)
    changed = CertificateAssessment.query.filter(CertificateAssessment.id == row.id, eligible).update(
        {"status": "processing", "lease_token": token, "lease_until": now + timedelta(seconds=seconds),
         "attempts": CertificateAssessment.attempts + 1}, synchronize_session=False)
    db.session.commit()
    if not changed:
        return True
    db.session.refresh(row)
    row_id, version = row.id, row.version
    sources, claims, root = list(row.sources), dict(row.claims), contained(artifact_root(app), row.artifact_key)
    attempts = row.attempts
    db.session.rollback()

    def current():
        return CertificateAssessment.query.filter_by(id=row_id, version=version, lease_token=token, status="processing")

    def heartbeat():
        renewed = current().update({"lease_until": utcnow() + timedelta(seconds=seconds)}, synchronize_session=False)
        db.session.commit()
        if not renewed:
            raise RuntimeError("识别任务已被新版本替代")

    try:
        if attempts > app.config.get("AUTOMATION_MAX_ATTEMPTS", 3):
            raise RuntimeError("识别多次超时，请重试或人工核验")
        # 模型仅存在于工作进程；人工项目根本不会进入此队列。
        from .pipeline import process_sources
        report = process_sources(sources, root, token, provider, claims, app.config, heartbeat)
        status, error = report["status"], None
    except Exception as exc:
        report, status, error = None, "failed", str(exc)[:2000]
    current().update({"report": report, "status": status, "error": error,
                      "lease_token": None, "lease_until": None}, synchronize_session=False)
    db.session.commit()
    return True
