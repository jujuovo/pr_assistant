"""Authenticated asynchronous OCR for the seven merged sample categories."""
from flask import Blueprint, abort, jsonify, request, send_file
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError
from services.competition_ocr.mapping import TARGETS
from extensions import db
from services.actors import actor
from services.private_paths import contained
from services.competition_ocr.catalog import CATEGORIES
from services.competition_ocr.paths import file_sha256
from services.competition_ocr.jobs import authorized_job, enqueue, job_root, job_view
from services.competition_ocr.service import MAX_BYTES

ocr_bp = Blueprint("ocr", __name__, url_prefix="/api/ocr")


@ocr_bp.errorhandler(HTTPException)
def http_error(error):
    db.session.rollback()
    return jsonify({"error": error.description}), error.code


@ocr_bp.errorhandler(ValueError)
def invalid(error):
    db.session.rollback()
    return jsonify({"error": str(error)}), 400


@ocr_bp.errorhandler(IntegrityError)
def conflict(error):
    db.session.rollback()
    return jsonify({"error": "关联发生并发冲突，请刷新后重试"}), 409


@ocr_bp.get("/categories")
def categories():
    actor()
    return jsonify({"categories": [{"key": c.key, "name": c.name, "kind": c.kind, "material_categories": TARGETS[c.key]}
                                    for c in CATEGORIES.values()]})


@ocr_bp.post("/<key>/recognize")
def recognize(key):
    actor()
    if key not in CATEGORIES:
        abort(404)
    if request.mimetype == "multipart/form-data":
        files = request.files.getlist("file")
        if len(files) != 1 or set(request.files) != {"file"}:
            raise ValueError("请使用 file 字段上传一张图片")
        payload, name = files[0].stream.read(MAX_BYTES + 1), files[0].filename
    else:
        extensions = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
                      "image/bmp": ".bmp", "image/tiff": ".tiff"}
        if request.mimetype not in extensions:
            abort(415, description="请上传图片或 multipart 的 file 字段")
        payload = request.stream.read(MAX_BYTES + 1)
        name = "upload" + extensions[request.mimetype]
    if len(payload) > MAX_BYTES:
        abort(413, description="图片不得超过10MB")
    return jsonify(job_view(enqueue(key, payload, name))), 202


@ocr_bp.get("/jobs/<job_id>")
def result(job_id):
    return jsonify(job_view(authorized_job(job_id)))


@ocr_bp.get("/jobs/<job_id>/mapping")
def mapping(job_id):
    row = authorized_job(job_id)
    return jsonify({"job_id": row.id, "status": row.status, "mapping": job_view(row)["mapping"]})


@ocr_bp.post("/jobs/<job_id>/confirm-material")
def confirm_material(job_id):
    from services.competition_ocr.binding import confirm
    from services.materials.service import body, view
    payload = body()
    row = confirm(job_id, payload)
    return jsonify({"job_id": job_id, "material": view(row)}), 200 if "material_record_id" in payload else 201


@ocr_bp.get("/jobs/<job_id>/images/<name>")
def image(job_id, name):
    row = authorized_job(job_id)
    relative = (row.report or {}).get("images", {}).get(name)
    if not relative:
        abort(404)
    try:
        path = contained(job_root(row.id), relative)
    except ValueError:
        abort(404)
    if not path.is_file():
        abort(404)
    if name == "original" and file_sha256(path) != row.sha256:
        abort(409, description="原件校验失败，请重新上传")
    response = send_file(path)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


from use_cases.materials import MaterialUseCaseError
from use_cases.cycles import CycleUseCaseError

@ocr_bp.errorhandler(MaterialUseCaseError)
def material_workflow_error(error):
    db.session.rollback()
    return jsonify({"error": str(error), "code": error.code}), error.status_code

@ocr_bp.errorhandler(CycleUseCaseError)
def cycle_workflow_error(error):
    db.session.rollback()
    return jsonify({"error": str(error), "code": error.code}), 409
