"""Versioned volunteer OCR queue, exact comparisons and manual appeal projection."""
from hashlib import sha256
from decimal import Decimal
from pathlib import Path
import json
from automation_models import utcnow
from extensions import db
from material_models import MaterialRecord, MaterialEvent
from ocr_models import OCRJob
from services.competition_ocr.jobs import enqueue, job_root
from services.competition_ocr.catalog import IMAGE_EXTENSIONS

LABELS = {"hours": "本次工时（小时）", "service_type": "工时类别", "award_date": "服务记录日期"}
KINDS = {"regular": "普通志愿服务", "reduced": "大型赛会或支教"}


def input_digest(row):
    value = {"data": row.data, "attachments": [(a.id, a.sha256, a.size) for a in row.attachments]}
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def queue(row, user, created_dirs):
    """Part of the caller's material transaction; never commits or owns the HTTP request."""
    from services.materials.service import stored_path
    from services.materials.originals import verify_ocr_originals
    verify_ocr_originals(row)
    meta = {"status": "queued", "material_version": row.version, "input_digest": input_digest(row),
            "jobs": [], "reasons": [], "comparisons": [], "auto_returned": False}
    analysis = {k: v for k, v in (row.analysis or {}).items() if k not in {"volunteer_ocr", "volunteer_appeal"}}
    row.ocr_raw_terms = None
    hashes = set()
    for attachment in row.attachments:
        if attachment.sha256 in hashes:
            meta["reasons"].append("存在重复图片，请删除重复材料后重新申报或提出申诉")
            continue
        hashes.add(attachment.sha256)
        if Path(attachment.filename).suffix.lower() not in IMAGE_EXTENSIONS:
            meta["reasons"].append(f"{attachment.filename}：暂不支持此格式的OCR，请申诉转人工核验")
            continue
        payload = stored_path(attachment.stored_name).read_bytes()
        try:
            job = enqueue("volunteer", payload, attachment.filename, commit=False,
                          material=row, attachment=attachment)
        except ValueError:
            meta["reasons"].append(f"{attachment.filename}：图片损坏或尺寸不合格，无法识别")
            continue
        created_dirs.append(job_root(job.id))
        meta["jobs"].append(job.id)
    row.analysis = {**analysis, "volunteer_ocr": meta}
    db.session.flush()
    if not meta["jobs"]:
        finish(row, meta, [], user.id)
    return meta


def _hours(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result > 0 else None
    except ArithmeticError:
        return None


def _kind_label(kinds):
    if not kinds or None in kinds:
        return None
    return "、".join(KINDS[kind] for kind in sorted(kinds))


def comparisons(row, jobs):
    totals = {"regular": Decimal(0), "reduced": Decimal(0)}
    amounts, kinds, dates, reasons = [], [], [], []
    reliable = {field: bool(jobs) for field in LABELS}
    for job in jobs:
        report = job.report or {}
        fields = report.get("fields") or {}
        amount, kind, day = _hours(fields.get("hours")), fields.get("service_type"), fields.get("award_date")
        amounts.append(amount)
        kinds.append(kind if kind in KINDS else None)
        dates.append(day)
        if amount is not None and kind in KINDS:
            totals[kind] += amount
        missing = set(report.get("missing_fields") or ())
        invalid = {"hours": amount is None, "service_type": kind not in KINDS, "award_date": not day}
        unavailable = [LABELS[field] for field in LABELS if invalid[field] or field in missing or job.status == "failed"]
        for field in LABELS:
            reliable[field] &= not (invalid[field] or field in missing or job.status == "failed")
        if unavailable:
            reasons.append(f"{job.filename}：未可靠识别" + "、".join(unavailable))
    recognized = {
        "hours": str(sum(amounts, Decimal(0))) if amounts and all(v is not None for v in amounts) else None,
        "service_type": _kind_label(set(kinds)),
        "award_date": dates[0] if dates and all(dates) and len(set(dates)) == 1 else None,
    }
    declared_hours = {kind: Decimal(row.data.get(kind+"_hours", "0")) for kind in KINDS}
    declared = {"hours": str(sum(declared_hours.values())),
                "service_type": _kind_label({kind for kind, value in declared_hours.items() if value > 0}),
                "award_date": row.data.get("award_date")}
    labels = dict(LABELS)
    if len(set(kinds)-{None}) > 1 or all(v > 0 for v in declared_hours.values()):
        for kind in KINDS:
            field = kind+"_hours"
            labels[field] = KINDS[kind]+"工时"
            declared[field] = str(declared_hours[kind])
            recognized[field] = str(totals[kind]) if reliable["hours"] and reliable["service_type"] else None
            reliable[field] = reliable["hours"] and reliable["service_type"]
    rows = []
    for field, label in labels.items():
        expected, actual = declared[field], recognized[field]
        equal = actual is not None and (Decimal(expected) == Decimal(actual) if field == "hours" or field.endswith("_hours") else expected == actual)
        match = bool(equal and reliable[field])
        reason = "matched" if match else "missing" if actual is None else "unreliable" if not reliable[field] else "mismatch"
        rows.append({"field": field, "label": label, "declared": expected, "recognized": actual, "matches": match, "reason": reason})
        if not match:
            reasons.append(f"{label}未可靠识别，无法核对" if reason == "missing" else f"{label}识别依据不足，需人工核验" if reason == "unreliable" else f"{label}与申报信息不一致")
    return rows, reasons


def finish(row, meta, jobs, actor_id):
    from use_cases.materials import _cas_change
    rows, reasons = comparisons(row, jobs)
    reasons = list(dict.fromkeys([*meta["reasons"], *reasons]))
    if not jobs and not reasons:
        reasons.append("没有可识别的证明图片")
    status = "returned" if reasons else "matched"
    updated = {**meta, "status": status, "comparisons": rows, "reasons": reasons,
               "auto_returned": bool(reasons), "material_version": row.version + 1}
    raw = {"reports": [{"job_id": j.id, "filename": j.filename, "report": j.report, "error": j.error} for j in jobs]}
    _cas_change(row, row.version, ("draft",), {"analysis": {**row.analysis, "volunteer_ocr": updated},
        "ocr_raw_terms": raw, "status": "needs_correction" if reasons else "draft"})
    db.session.add(MaterialEvent(record_id=row.id, actor_id=actor_id,
        action="ocr_returned" if reasons else "ocr_matched",
        details={"version": row.version, "comparisons": rows, "reasons": reasons, "authenticity": "not_assessed"}))


def publish(job):
    """Lease fencing happens in the worker; stale material versions cannot be changed."""
    row = MaterialRecord.query.filter_by(id=job.material_record_id).with_for_update().populate_existing().one_or_none()
    if row is None or row.category != "volunteer" or row.status != "draft" or row.version != job.material_version:
        return
    meta = (row.analysis or {}).get("volunteer_ocr") or {}
    if job.id not in meta.get("jobs", []) or meta.get("input_digest") != input_digest(row):
        return
    jobs = OCRJob.query.filter(OCRJob.id.in_(meta["jobs"])).populate_existing().all()
    if any(j.status in {"queued", "processing"} for j in jobs):
        return
    finish(row, meta, jobs, job.user_id)


def projection(row, user, actions):
    """One backend authority for client states and appeal/submit commands."""
    meta = dict((row.analysis or {}).get("volunteer_ocr") or {})
    appeal = (row.analysis or {}).get("volunteer_appeal")
    current = bool(meta) and meta.get("input_digest") == input_digest(row)
    if current and meta.get("status") == "queued" and meta.get("material_version") != row.version:
        current = False
        meta["status"] = "stale"
    state = {"submitted": "pending_review", "under_review": "pending_review", "scored": "approved",
             "verified": "approved", "verified_not_eligible": "approved_ineligible", "rejected": "rejected"}.get(row.status, row.status)
    owner = user.role == "student" and user.student_id == row.student_id
    if row.status == "draft":
        if current and meta.get("status") == "matched":
            state = "ready_to_submit"
        else:
            actions = tuple(a for a in actions if a != "submit")
            if current and meta.get("status") == "queued":
                running = OCRJob.query.filter(OCRJob.id.in_(meta.get("jobs", [])), OCRJob.status == "processing").first()
                state = "ocr_running" if running else "ocr_queued"
            elif owner and row.attachments:
                actions = (*actions, "recognize")
    if owner and row.status == "needs_correction" and current and meta.get("auto_returned") and not appeal:
        actions = (*actions, "appeal", "recognize")
    return {"workflow_state": state, "volunteer_ocr": meta or None,
            "appeal": appeal, "priority_review": bool(appeal)}, actions


def assert_gate(row):
    from use_cases.materials import MaterialUseCaseError
    meta = (row.analysis or {}).get("volunteer_ocr") or {}
    appeal = (row.analysis or {}).get("volunteer_appeal") or {}
    if meta.get("input_digest") != input_digest(row) or not (
        meta.get("status") == "matched" or (meta.get("auto_returned") and appeal.get("reason"))
    ):
        raise MaterialUseCaseError("请等待OCR比对完成；被打回的材料请修改后重识别，或提交申诉转人工审核", code="volunteer_ocr_required", status_code=409)
