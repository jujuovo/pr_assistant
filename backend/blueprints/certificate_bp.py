"""学生/同院教师访问持久化证书结果和受保护原件。"""
from flask import Blueprint, abort, jsonify, request, send_file
from werkzeug.exceptions import HTTPException
from extensions import db
from models import Application
from certificate_models import CertificateAssessment
from services.automation import actor
from services.certificates.service import (CATALOG, authorize_application, enqueue, view,
                                           artifact_root, contained)

certificate_bp = Blueprint("certificates", __name__, url_prefix="/api/certificates")


@certificate_bp.errorhandler(HTTPException)
def api_error(error):
    db.session.rollback()
    return jsonify({"error": error.description}), error.code


@certificate_bp.get("/catalog")
def catalog():
    actor()
    return jsonify({"projects": CATALOG})


def row_for(application_id):
    application = db.get_or_404(Application, application_id)
    authorize_application(application)
    return CertificateAssessment.query.filter_by(application_id=application_id).first(), application


@certificate_bp.get("/applications/<int:application_id>")
def assessment(application_id):
    row, _ = row_for(application_id)
    return jsonify(view(row) if row else {"status": "manual", "project": "manual", "report": None})


@certificate_bp.post("/applications/<int:application_id>/retry")
def retry(application_id):
    row, application = row_for(application_id)
    if not row or row.project_key == "manual":
        abort(409, description="人工通道不运行自动识别")
    if row.claims.get("preview_flow"):
        abort(409, description="预览流程请重新选择材料，保留已确认的OCR与申报快照")
    if application.status not in ("draft", "pending"):
        abort(409, description="已审核申请不能重跑；请保留原审核证据")
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict) or type(body.get("version")) is not int:
        abort(400, description="重跑必须提交整数版本号")
    changed = CertificateAssessment.query.filter_by(id=row.id, version=body.get("version")).filter(
        CertificateAssessment.status.notin_(["queued", "processing"])).update(
        {"version": CertificateAssessment.version + 1}, synchronize_session=False)
    if not changed:
        abort(409, description="识别正在运行或版本已变化，请刷新")
    db.session.refresh(row)
    enqueue(application, row.project_key, {k: v for k, v in row.claims.items() if k in ("award", "region", "group", "track")})
    db.session.commit()
    return jsonify(view(row)), 202


@certificate_bp.get("/applications/<int:application_id>/artifacts/<int:version>/<path:filename>")
def artifact(application_id, version, filename):
    row, _ = row_for(application_id)
    if not row or version != row.version:
        abort(404)
    allowed = {s["relative"] for s in row.sources}
    if row.report:
        for page in row.report.get("pages", []):
            allowed.update(page.get("artifacts", {}).values())
    if filename not in allowed:
        abort(404)
    root = contained(artifact_root(), row.artifact_key)
    try:
        path = contained(root, filename)
    except ValueError:
        abort(404)
    if not path.is_file():
        abort(404)
    response = send_file(path, conditional=True)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@certificate_bp.post('/previews')
def preview_upload():
    from services.certificates.preview import create_preview
    return jsonify(view(create_preview(request.files.getlist('files')))), 202


@certificate_bp.post('/applications/<int:application_id>/confirm-preview')
def confirm_preview(application_id):
    from services.certificates.preview import save_preview
    row, application = row_for(application_id)
    result = save_preview(row, application, request.get_json(silent=True))
    return jsonify(view(result))
