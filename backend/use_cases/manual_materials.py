"""Manual verification outside the scoring workflow; transport stays in Blueprints."""
from services.materials.ocr_schemas import MANUAL_TYPES
from services.materials.schemas import text
from use_cases.materials import MaterialUseCaseError, _authorize_transition, _cas_change, _event


def is_manual(row):
    return row.category in MANUAL_TYPES or (row.category == "student_work" and
        (isinstance(row.ocr_raw_terms, dict) or (row.analysis or {}).get("manual_only") is True)
        and row.rule_version_id is None)


def submit_manual(user, row, version):
    _authorize_transition(user, row, "submit", "submitted")
    if row.category == "arts_sports" and not row.attachments:
        raise MaterialUseCaseError("文体活动材料至少需要一个证明原件", code="material_attachment_required")
    from services.materials.originals import verify_ocr_originals
    verify_ocr_originals(row)
    _cas_change(row, version, ("draft",), {"status": "submitted"})
    _event(row, user, "submitted", {"version": row.version, "manual_only": True})


def review_manual(user, row, payload):
    from use_cases.staged_review import assert_final_review
    assert_final_review(user, row)
    if user.role not in {"teacher", "admin"} or user.faculty_id != row.faculty_id:
        raise MaterialUseCaseError("没有本学院材料核验权限", code="forbidden", status_code=403)
    import hashlib
    import json
    from extensions import db
    from workflow_models import MaterialReviewCommand
    key = text(payload.get('idempotency_key') or f'manual:{user.id}:{payload["version"]}', '幂等键', maximum=128)
    digest = hashlib.sha256(json.dumps([row.id, user.id, payload], sort_keys=True).encode()).hexdigest()
    previous = MaterialReviewCommand.query.filter_by(record_id=row.id, idempotency_key=key).first()
    if previous:
        if previous.request_digest != digest:
            raise MaterialUseCaseError('幂等键冲突', code='idempotency_conflict', status_code=409)
        return True
    if payload["decision"] not in ("verified", "rejected", "needs_correction"):
        raise MaterialUseCaseError("人工核验结论无效")
    comment = text(payload.get("comment", ""), "核验意见", required=payload["decision"] != "verified", maximum=2000)
    from services.materials.originals import verify_ocr_originals
    verify_ocr_originals(row)
    target = 'needs_correction' if payload['decision'] == 'rejected' else payload['decision']
    _cas_change(row, payload["version"], ("submitted", "under_review"), {"status": target})
    from services.competition_ocr.binding import record_links
    _event(row, user, "reviewed", {"version": row.version, "decision": payload['decision'], "comment": comment,
        "manual_only": True, "data_snapshot": row.data, "ocr_links_snapshot": record_links(row),
        "attachments_snapshot": [{"id": a.id, "filename": a.filename, "size": a.size, "sha256": a.sha256}
                                 for a in row.attachments]})
    db.session.add(MaterialReviewCommand(record_id=row.id, idempotency_key=key, request_digest=digest,
        result={'version': row.version, 'status': row.status, 'review_stage': row.review_stage}, created_by=user.id))
    db.session.flush()
    return False
