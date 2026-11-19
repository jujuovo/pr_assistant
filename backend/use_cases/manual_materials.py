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
    from services.materials.originals import verify_ocr_originals
    verify_ocr_originals(row)
    _cas_change(row, version, ("draft",), {"status": "submitted"})
    _event(row, user, "submitted", {"version": row.version, "manual_only": True})


def review_manual(user, row, payload):
    if user.role not in {"teacher", "admin"} or user.faculty_id != row.faculty_id:
        raise MaterialUseCaseError("没有本学院材料核验权限", code="forbidden", status_code=403)
    if payload["decision"] not in ("verified", "rejected", "needs_correction"):
        raise MaterialUseCaseError("人工核验结论无效")
    comment = text(payload["comment"], "核验意见", maximum=2000)
    from services.materials.originals import verify_ocr_originals
    verify_ocr_originals(row)
    _cas_change(row, payload["version"], ("submitted",), {"status": payload["decision"]})
    from services.competition_ocr.binding import record_links
    _event(row, user, "reviewed", {"version": row.version, "decision": row.status, "comment": comment,
        "manual_only": True, "data_snapshot": row.data, "ocr_links_snapshot": record_links(row),
        "attachments_snapshot": [{"id": a.id, "filename": a.filename, "size": a.size, "sha256": a.sha256}
                                 for a in row.attachments]})
