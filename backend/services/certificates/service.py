"""白名单路由、原件快照和权限检查；HTTP 进程不加载 OCR 模型。"""
import hashlib
import uuid
from pathlib import Path
from flask import abort, current_app
from extensions import db
from certificate_models import CertificateAssessment
from services.automation import actor

CATALOG = [{"key": "lanqiao", "name": "蓝桥杯（已适配样本模板）", "automatic_assistance": True,
            "note": "仅辅助核对已适配的图片/PDF模板，水印匹配不能证明证书真实。"}]


def authorize_application(application, reviewer=False):
    user = actor()
    if user.role == "student" and not reviewer and user.student_id == application.student_id:
        return user
    if user.role in ("teacher", "admin") and user.faculty_id == application.faculty_id:
        return user
    abort(403, description="没有该申请的证书材料权限")


def validate_selection(data):
    key = data.get("certificateProject", data.get("certificate_project", "manual"))
    if key not in ("manual", "lanqiao"):
        abort(400, description="项目不在自动辅助白名单内，请选择人工通道")
    claims = data.get("certificateClaims", data.get("certificate_claims", {}))
    if not isinstance(claims, dict) or any(k not in ("award", "region", "group", "track") for k in claims):
        abort(400, description="证书申报字段无效")
    if any(not isinstance(v, str) or len(v) > 100 for v in claims.values()):
        abort(400, description="证书申报字段必须为100字以内的文字")
    return key, claims


def artifact_root(app=None):
    config = (app or current_app).config
    return Path(config.get("CERTIFICATE_STORAGE_FOLDER", Path(config["AUTOMATION_UPLOAD_FOLDER"]).parent / "private-certificates")).resolve()


def contained(root, relative):
    path = (root / relative).resolve()
    if path == root or root not in path.parents:
        raise ValueError("证书文件路径越界")
    return path


def enqueue(application, key, claims):
    """每次修改生成不可变原件快照；旧 worker 的令牌不能提交到新版本。"""
    row = CertificateAssessment.query.filter_by(application_id=application.id).first()
    if not row:
        row = CertificateAssessment(application_id=application.id)
        db.session.add(row)
    row.project_key, row.claims = key, dict(claims)
    row.claims.update(student=application.student_name, category=application.application_type,
                     rule_id=application.rule_id, coefficients=application.dynamic_coefficients,
                     expected_score=application.self_score)
    row.artifact_key = str(uuid.uuid4())
    row.version = (row.version or 0) + 1
    row.attempts, row.lease_token, row.lease_until, row.error = 0, None, None, None
    row.report, row.sources = None, []
    if key == "manual":
        row.status = "manual"
        row.report = {"message": "该项目完全走人工核验通道，不计算自动判断置信度。", "authenticity": "not_assessed"}
        return row
    root = artifact_root()
    folder = contained(root, row.artifact_key)
    folder.mkdir(parents=True, exist_ok=False)
    upload_root = Path(current_app.config["FILE_FOLDER"]).resolve()
    sources = []
    for i, attachment in enumerate(application.files or []):
        name = attachment.get("name", "")
        # 仅接受由本申请保存的附件记录，拒绝任意 URL、相对路径和符号链接越界。
        if not isinstance(name, str) or Path(name).name != name or attachment.get("path") != f"/uploads/files/{name}":
            raise ValueError("证书附件记录无效")
        source = contained(upload_root, name)
        if not source.is_file():
            raise ValueError("证书附件不存在")
        limit = current_app.config.get("CERTIFICATE_MAX_FILE_BYTES", 10 * 1024 * 1024)
        if source.stat().st_size > limit:
            raise ValueError("证书自动识别单个文件不得超过10MB，请使用人工通道")
        payload = source.read_bytes()
        suffix = source.suffix.lower()
        original = folder / f"original-{i}{suffix}"
        original.write_bytes(payload)
        sources.append({"name": name, "relative": original.name, "sha256": hashlib.sha256(payload).hexdigest()})
    row.sources = sources
    row.status = "queued" if sources else "manual_review"
    if not sources:
        row.report = {"message": "没有证书附件，请上传材料或人工核验。", "authenticity": "not_assessed", "pages": []}
    return row


def selection_present(data):
    return "certificateProject" in data or "certificate_project" in data


def selection_json(application):
    row = CertificateAssessment.query.filter_by(application_id=application.id).first()
    if not row:
        return {}
    return {"certificateProject": row.project_key,
            "certificateClaims": {k: v for k, v in row.claims.items() if k in ("award", "region", "group", "track")}}


def view(row):
    return {"id": row.id, "application_id": row.application_id, "project": row.project_key,
            "status": row.status, "version": row.version, "claims": row.claims,
            "report": row.report, "error": row.error,
            "preview_flow": bool(row.claims.get("preview_flow")),
            "student_values": row.claims.get("student_values"),
            "application_status": row.application.status, "authenticity": "not_assessed"}
