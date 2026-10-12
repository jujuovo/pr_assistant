"""后端提供预览表格数据；不改变前端、不在 HTTP 请求里运行 OCR。"""
import hashlib
import io
import json
import uuid
from pathlib import Path
from flask import Blueprint, abort, current_app, jsonify, request, send_file
from PIL import Image, UnidentifiedImageError
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError
from extensions import db
from models import Student, Application
from automation_models import AutomationBatch, AutomationItem, AutomationPolicy, AutomationReview
from services.automation import (actor, authorize, number, reserve, preview, validate_policy,
                                 policy_for, value, review_batch, claim_transition, check_credit_hours, split_remaining)

automation_bp = Blueprint("automation", __name__, url_prefix="/api/automation")


@automation_bp.errorhandler(HTTPException)
def api_error(error):
    db.session.rollback()
    return jsonify({"error": error.description}), error.code


def batch_at(batch_id):
    batch = db.get_or_404(AutomationBatch, batch_id)
    authorize(batch)
    return batch


def year_value(raw):
    try:
        year = int(str(raw))
        if not 2000 <= year <= 2100:
            raise ValueError()
        return year
    except (TypeError, ValueError):
        abort(400, description="year 必须为2000至2100的政策年度")


@automation_bp.errorhandler(IntegrityError)
def conflict(error):
    db.session.rollback()
    return jsonify({"error": "记录发生并发冲突，请刷新后重试"}), 409


@automation_bp.route("/volunteer/policies/<int:year>", methods=["GET", "PUT"])
def policies(year):
    user = actor()
    year = year_value(year)
    if not user.faculty_id:
        abort(400, description="账号未关联学院")
    if request.method == "GET":
        policy = AutomationPolicy.query.filter_by(faculty_id=user.faculty_id, year=year).first()
        return jsonify({"policy": policy.config if policy else None,
                        "revision": policy.revision if policy else None})
    if user.role != "admin":
        abort(403, description="仅学院管理员可设置政策")
    config = validate_policy(request.get_json(silent=True))
    policy = AutomationPolicy.query.filter_by(faculty_id=user.faculty_id, year=year).with_for_update().first()
    if AutomationBatch.query.filter(AutomationBatch.faculty_id == user.faculty_id,
                                    AutomationBatch.year == year, AutomationBatch.application_id.isnot(None)).first():
        abort(409, description="该年度已有提交申请，政策已冻结；请使用新的政策年度")
    if policy:
        policy.config, policy.revision = config, policy.revision + 1
    else:
        policy = AutomationPolicy(faculty_id=user.faculty_id, year=year, config=config)
        db.session.add(policy)
    db.session.commit()
    return jsonify({"policy": config, "revision": policy.revision})


@automation_bp.post("/volunteer/batches")
def upload_batch():
    user = actor()
    if user.role != "student" or not user.student_id or not user.faculty_id:
        abort(403, description="仅关联学院及学号的学生可上传")
    aliases = {"credit": "volunteer_credit", "honor": "volunteer_honor",
               "volunteer_credit": "volunteer_credit", "volunteer_honor": "volunteer_honor"}
    choices = request.form.getlist("material_type")
    if len(choices) != 1 or choices[0] not in aliases:
        abort(400, description="每批必须只选择一种 material_type：credit 或 honor")
    year = year_value(request.form.get("year"))
    files = request.files.getlist("files")
    if not files or len(files) > current_app.config["AUTOMATION_MAX_FILES"]:
        abort(400, description="图片数量为空或超过批次限制")
    try:
        claims = json.loads(request.form.get("claimed_hours", "null"))
    except (ValueError, TypeError):
        abort(400, description="claimed_hours 应为与文件一一对应的 JSON 数组")
    if claims is not None and (not isinstance(claims, list) or len(claims) != len(files)):
        abort(400, description="claimed_hours 必须与文件数量一致")
    claims = [number(x) if x is not None else None for x in claims] if claims is not None else [None] * len(files)
    for claim in claims:
        check_credit_hours(aliases[choices[0]], claim)
    validated = []
    for uploaded, claim in zip(files, claims):
        content = uploaded.read(current_app.config["AUTOMATION_MAX_IMAGE_BYTES"] + 1)
        if not content or len(content) > current_app.config["AUTOMATION_MAX_IMAGE_BYTES"]:
            abort(400, description="图片为空或超过单文件限制")
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in ("JPEG", "PNG", "WEBP", "BMP") or getattr(image, "n_frames", 1) != 1:
                    abort(400, description="仅接受单页 JPG/PNG/WEBP/BMP 图片")
                if image.width * image.height > current_app.config["AUTOMATION_MAX_PIXELS"]:
                    abort(400, description="图片像素过大")
                suffix = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp"}[image.format]
                image.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            abort(400, description="图片损坏或格式无效")
        validated.append((uploaded.filename or "image", content, suffix, claim))
    folder = Path(current_app.config["AUTOMATION_UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    batch = AutomationBatch(student_id=user.student_id, faculty_id=user.faculty_id, year=year,
                            material_type=aliases[choices[0]])
    db.session.add(batch)
    db.session.flush()
    created_paths = []
    try:
        for filename, content, suffix, claim in validated:
            digest = hashlib.sha256(content).hexdigest()
            item = AutomationItem(batch_id=batch.id, filename=Path(filename).name[:255], sha256=digest, claimed_hours=claim)
            db.session.add(item)
            db.session.flush()
            duplicate = reserve(item, "file", digest)
            if duplicate:
                item.status, item.duplicate_of = "duplicate", duplicate
            else:
                item.stored_name = uuid.uuid4().hex + suffix
                path = folder / item.stored_name
                path.write_bytes(content)
                created_paths.append(path)
        if all(x.status == "duplicate" for x in batch.items):
            batch.status = "completed"
        db.session.commit()
    except Exception:
        db.session.rollback()
        for path in created_paths:
            path.unlink(missing_ok=True)
        raise
    return jsonify(preview(batch)), 202


@automation_bp.get("/volunteer/batches")
def list_batches():
    user = actor()
    query = AutomationBatch.query
    if user.role == "student":
        query = query.filter_by(student_id=user.student_id)
    elif user.role in ("admin", "teacher") and user.faculty_id:
        query = query.filter_by(faculty_id=user.faculty_id)
    else:
        abort(403)
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        abort(400)
    rows = query.order_by(AutomationBatch.id.desc()).offset((page - 1) * 20).limit(20).all()
    return jsonify({"page": page, "batches": [{"id": b.id, "status": b.status, "material_type": b.material_type,
                    "year": b.year, "application_id": b.application_id, "version": b.version} for b in rows]})


@automation_bp.get("/volunteer/batches/<int:batch_id>")
def batch_preview(batch_id):
    return jsonify(preview(batch_at(batch_id)))


@automation_bp.get("/items/<int:item_id>/image")
def material_image(item_id):
    item = db.get_or_404(AutomationItem, item_id)
    authorize(item.batch)
    if not item.stored_name and item.duplicate_of:
        item = db.get_or_404(AutomationItem, item.duplicate_of)
        authorize(item.batch)
    if not item.stored_name:
        abort(404)
    response = send_file(Path(current_app.config["AUTOMATION_UPLOAD_FOLDER"]) / item.stored_name)
    response.headers["Cache-Control"] = "private, no-store"
    return response


@automation_bp.get("/items/<int:item_id>/evidence")
def evidence(item_id):
    item = db.get_or_404(AutomationItem, item_id)
    authorize(item.batch)
    return jsonify({"report": item.report, "ocr": item.raw_ocr})


@automation_bp.post("/volunteer/batches/<int:batch_id>/retry")
def retry(batch_id):
    batch = batch_at(batch_id)
    data = request.get_json(silent=True)
    data = {} if data is None else data
    if not isinstance(data, dict):
        abort(400, description="重试数据必须是对象")
    claim_transition(batch, data.get("version", batch.version), ("failed", "completed"),
                     unsubmitted=True, next_status="queued")
    retryable = [x for x in batch.items if x.status in ("failed", "incomplete")]
    if not retryable:
        abort(409, description="没有失败或不完整项可重试；重复或类型错误项不能通过重试绕过")
    for item in retryable:
        item.status, item.error = "queued", None
    batch.status, batch.attempts, batch.error = "queued", 0, None
    batch.lease_token = batch.lease_until = None
    db.session.commit()
    return jsonify(preview(batch)), 202


@automation_bp.post("/volunteer/batches/<int:batch_id>/submit")
def submit(batch_id):
    batch = batch_at(batch_id)
    user = actor()
    if user.role != "student":
        abort(403)
    data = request.get_json(silent=True)
    data = {} if data is None else data
    if not isinstance(data, dict):
        abort(400)
    claim_transition(batch, data.get("version"), ("completed",), unsubmitted=True)
    policy = AutomationPolicy.query.filter_by(faculty_id=batch.faculty_id, year=batch.year).with_for_update().first()
    if not policy:
        abort(409, description="管理员尚未配置加分政策")
    view = preview(batch)
    eligible = {row["id"] for row in view["rows"] if row["can_submit"]}
    ids = data.get("item_ids", sorted(eligible))
    if not isinstance(ids, list) or not ids or any(not isinstance(x, int) or isinstance(x, bool) for x in ids):
        abort(400, description="请选择可提交的明细")
    if len(set(ids)) != len(ids) or not set(ids) <= eligible:
        abort(409, description="重复、类型错误、不在认定范围或识别不完整的明细不得提交")
    student = db.session.get(Student, user.student.id) if user.student else None
    if not student or not student.department_id or not student.major_id:
        abort(400, description="请先完善学生专业信息")
    selected_view = preview(batch, item_ids=ids)
    application = Application(student_id=user.student_id, student_name=user.name, faculty_id=user.faculty_id,
                              department_id=student.department_id, major_id=student.major_id,
                              application_type="comprehensive", project_name=f"{batch.year}年度志愿工时（批次{batch.id}）",
                              status="pending", self_score=float(selected_view["estimated_incremental_score"] or 0),
                              description="自动识别仅为辅助，逐项核定后按年度共用上限计分", files=[],
                              dynamic_coefficients={"project_category": "volunteer", "automation_batch_id": batch.id})
    db.session.add(application)
    db.session.flush()
    batch.application_id, batch.status = application.id, "submitted"
    batch.policy_snapshot = {"revision": policy.revision, **policy.config}
    for item in batch.items:
        item.submitted = item.id in ids
    split_remaining(batch, user)
    db.session.commit()
    return jsonify(preview(batch)), 201


@automation_bp.post("/volunteer/batches/<int:batch_id>/reclassify")
def reclassify(batch_id):
    """纠正上传时选错的类型：重用原项，不通过重新上传绕过去重。"""
    batch = batch_at(batch_id)
    user = actor()
    if user.role != "student":
        abort(403)
    data = request.get_json(silent=True)
    data = {} if data is None else data
    if not isinstance(data, dict):
        abort(400)
    choices = {"credit": "volunteer_credit", "honor": "volunteer_honor"}
    if not isinstance(data.get("material_type"), str) or data["material_type"] not in choices:
        abort(400, description="material_type 必须为 credit/honor")
    claim_transition(batch, data.get("version"), ("completed",), unsubmitted=True, next_status="queued")
    old_type = batch.material_type
    batch.material_type = choices[data["material_type"]]
    batch.attempts = 0
    batch.lease_token = batch.lease_until = None
    for item in batch.items:
        if not item.duplicate_of and item.stored_name:
            item.status, item.error, item.report, item.raw_ocr = "queued", None, None, None
    db.session.add(AutomationReview(batch_id=batch.id, reviewer_id=user.id,
                     details={"action": "reclassify", "old_type": old_type, "new_type": batch.material_type}))
    db.session.commit()
    return jsonify(preview(batch)), 202


@automation_bp.post("/volunteer/batches/<int:batch_id>/review")
def review(batch_id):
    return jsonify(review_batch(batch_at(batch_id), request.get_json(silent=True)))
