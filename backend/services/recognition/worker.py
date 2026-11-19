"""数据库队列：CAS 原子领取、租约恢复及提交时令牌校验。"""
import json
import uuid
from pathlib import Path
from datetime import timedelta
from PIL import Image
from sqlalchemy import and_, or_
from extensions import db
from automation_models import AutomationBatch
from automation_models import utcnow
from services.recognition import recognize_fields
from services.recognition.serialization import json_safe
from services.automation import (reserve, semantic_key, honor_event_key, value, lock_student,
                                 existing_honor_record, cross_type_conflicts)
from services.volunteer_rules import parse_number


def _current_batch(batch_id, token):
    return AutomationBatch.query.filter_by(id=batch_id, lease_token=token, status="processing", application_id=None)


def _fail_exhausted_batch(batch, token):
    lock_student(batch.student_id)
    changed = _current_batch(batch.id, token).update(
        {"status": "failed", "error": "任务多次超时", "lease_token": None, "lease_until": None,
         "version": AutomationBatch.version + 1}, synchronize_session=False)
    if not changed:
        db.session.rollback()
        return
    for item in batch.items:
        if item.status == "queued":
            item.status, item.error = "failed", "识别租约多次超时，请重试或人工处理"
    db.session.commit()


def _recognize_item(provider, path, material_type, claim):
    try:
        with Image.open(path) as image:
            width = image.width
        data = json_safe(provider.predict(path))
        report = recognize_fields(material_type, data, width, float(claim) if claim is not None else None)
        report["ocr_model"] = "PP-OCRv5_mobile"
        json.dumps(report, allow_nan=False)
        return report, data, None
    except Exception as exc:
        return None, None, str(exc)[:2000]


def _reserve_activity(item, report, student, material_type):
    key = semantic_key(item)
    if not key:
        item.status, item.error = "incomplete", "缺少活动标识，无法排除重复，请补充完整截图"
        return
    extra_key = honor_event_key(item)
    duplicate = existing_honor_record(item, key, extra_key) or reserve(item, "activity", key)
    if not duplicate and extra_key:
        duplicate = reserve(item, "honor_event", extra_key)
    item.status = "duplicate" if duplicate else "ready"
    item.duplicate_of = duplicate
    conflicts = cross_type_conflicts(item) if not duplicate else []
    blocked = next((candidate for candidate in conflicts if candidate["blocking"]), None)
    if blocked:
        item.status, item.duplicate_of = "duplicate", blocked["id"]
    if conflicts:
        report["warnings"].append({"code": "cross_type_conflict", "message": "存在跨类型同日活动材料，必须排除重复认定"})
        item.report = dict(report)
    if material_type == "volunteer_honor" and value(item, "volunteer_name") != student.student_name:
        report["warnings"].append({"code": "name_mismatch", "message": "截图姓名与账号姓名不一致，必须核对原件"})
        item.report = dict(report)


def _apply_recognition(item, report, data, error, student, material_type):
    item.report, item.raw_ocr, item.error = report, data, error
    if error:
        item.status = "failed"
    elif report["page_type"] != ("credit" if material_type == "volunteer_credit" else "honor"):
        item.status = "wrong_type"
    elif value(item, "displayed_hours") is None or any(w.get("code") == "invalid_time_order" for w in report["warnings"]):
        item.status, item.error = "incomplete", "未可靠识别时数，不能自动提交"
    else:
        try:
            parse_number(value(item, "displayed_hours"))
        except ValueError as exc:
            item.status, item.error = "incomplete", str(exc)
            report["warnings"].append({"code": "invalid_hours", "message": str(exc)})
            item.report = dict(report)
            return
        _reserve_activity(item, report, student, material_type)


def run_one(app, provider):
    now = utcnow()
    lease_seconds = app.config["AUTOMATION_LEASE_SECONDS"]
    eligible = or_(AutomationBatch.status == "queued",
                   and_(AutomationBatch.status == "processing", AutomationBatch.lease_until < now))
    batch = AutomationBatch.query.filter(eligible, AutomationBatch.application_id.is_(None)).order_by(AutomationBatch.id).first()
    if not batch:
        return False
    token = str(uuid.uuid4())
    claimed = AutomationBatch.query.filter(AutomationBatch.id == batch.id, eligible,
                                           AutomationBatch.application_id.is_(None)).update(
        {"status": "processing", "lease_token": token, "lease_until": now + timedelta(seconds=lease_seconds),
         "attempts": AutomationBatch.attempts + 1}, synchronize_session=False)
    db.session.commit()
    if not claimed:
        return True
    db.session.refresh(batch)
    if batch.attempts > app.config["AUTOMATION_MAX_ATTEMPTS"]:
        _fail_exhausted_batch(batch, token)
        return True
    for item in batch.items:
        if item.status != "queued":
            continue
        item_id = item.id
        path = Path(app.config["AUTOMATION_UPLOAD_FOLDER"]) / item.stored_name
        material_type, claim = batch.material_type, item.claimed_hours
        # 模型推理时不持有数据库事务，避免阻塞 HTTP 请求。
        db.session.rollback()
        report, data, error = _recognize_item(provider, path, material_type, claim)
        # 超时的旧工作进程不能覆盖新结果；先续租，再写明细。
        student = lock_student(batch.student_id)
        locked = _current_batch(batch.id, token).update(
            {"lease_until": utcnow() + timedelta(seconds=lease_seconds)}, synchronize_session=False)
        if not locked:
            db.session.rollback()
            return True
        db.session.refresh(item)
        if item.id != item_id or item.status != "queued":
            db.session.rollback()
            return True
        _apply_recognition(item, report, data, error, student, material_type)
        db.session.commit()
    _current_batch(batch.id, token).update(
        {"status": "completed", "lease_token": None, "lease_until": None, "version": AutomationBatch.version + 1},
        synchronize_session=False)
    db.session.commit()
    return True
