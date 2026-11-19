"""Stable snake_case DTOs for the material-to-ranking workflow."""


ROLE_ACTIONS = {
    "student": {
        "material": {"edit", "submit", "withdraw", "reconfirm", "abandon", "view"},
        "score_snapshot": {"view"}, "rule_package": {"view"}, "ranking_batch": {"view"},
    },
    "teacher": {
        "material": {"view", "approve", "return", "open"},
        "score_snapshot": {"view"}, "rule_package": {"view"},
        "ranking_batch": {"view", "export"},
    },
    "admin": {
        "material": {"view"}, "score_snapshot": {"view", "recalculate_preview"},
        "rule_package": {"view", "copy", "edit", "diff", "validate", "publish"},
        "ranking_batch": {"view", "generate", "freeze", "request_correction",
                          "publish", "withdraw", "create_successor", "export"},
    },
}


def _value(source, key, default=None):
    return source.get(key, default) if isinstance(source, dict) else getattr(source, key, default)


def _time(value):
    if value is None or isinstance(value, str):
        return value
    return value.isoformat() + ("Z" if value.tzinfo is None else "")


def _authorize_scope(source, *, role, student_id=None, faculty_id=None):
    owner = _value(source, "student_id")
    faculty = _value(source, "faculty_id")
    if role == "student" and (not student_id or owner != student_id):
        raise PermissionError("student presentation is limited to self")
    if role in {"teacher", "admin"} and (not faculty_id or faculty != faculty_id):
        raise PermissionError("presentation is outside actor organization scope")


def _actions(kind, role, requested):
    permitted = ROLE_ACTIONS.get(role, {}).get(kind, set())
    return sorted(set(requested or ()) & permitted)


def material_presentation_dto(source, *, role, student_id=None, faculty_id=None):
    _authorize_scope(source, role=role, student_id=student_id, faculty_id=faculty_id)
    payload = {
        "kind": "material", "id": _value(source, "id"),
        "version": _value(source, "version"), "status": _value(source, "status"),
        "scope": {"student_id": _value(source, "student_id"),
                  "faculty_id": _value(source, "faculty_id"),
                  "cycle_code": _value(source, "year"),
                  "category": _value(source, "category")},
        "reason_code": _value(source, "reason_code"),
        "created_at": _time(_value(source, "created_at")),
        "updated_at": _time(_value(source, "updated_at")),
        "allowed_actions": _actions("material", role, _value(source, "allowed_actions", ())),
        "data": _value(source, "data", {}),
    }
    if role in {"teacher", "admin"}:
        payload["verification"] = _value(source, "verification")
    return payload


def score_presentation_dto(source, *, role, student_id=None, faculty_id=None):
    _authorize_scope(source, role=role, student_id=student_id, faculty_id=faculty_id)
    return {
        "kind": "score_snapshot", "id": _value(source, "snapshot_id", _value(source, "id")),
        "version": _value(source, "snapshot_version", _value(source, "version")),
        "status": _value(source, "status"),
        "scope": {"student_id": _value(source, "student_id"),
                  "faculty_id": _value(source, "faculty_id"),
                  "cycle_code": _value(source, "year")},
        "reason_code": _value(source, "reason_code"),
        "updated_at": _time(_value(source, "updated_at")),
        "allowed_actions": _actions("score_snapshot", role, _value(source, "allowed_actions", ())),
        "comprehensive_score": _value(source, "comprehensive_score"),
        "categories": _value(source, "categories", {}),
        "entries": _value(source, "entries", []),
    }


def rule_package_presentation_dto(source, *, role, faculty_id=None):
    scope_key = _value(source, "scope_key", "global")
    package_faculty = _value(source, "faculty_id")
    if package_faculty is not None and (role not in {"teacher", "admin"} or package_faculty != faculty_id):
        raise PermissionError("rule package is outside actor organization scope")
    return {
        "kind": "rule_package", "id": _value(source, "id"),
        "package_id": _value(source, "package_id"), "version": _value(source, "version"),
        "status": _value(source, "status"),
        "scope": {"cycle_code": _value(source, "cycle_code"), "scope_key": scope_key,
                  "faculty_id": package_faculty},
        "reason_code": _value(source, "reason_code"),
        "created_at": _time(_value(source, "created_at")),
        "published_at": _time(_value(source, "published_at")),
        "allowed_actions": _actions("rule_package", role, _value(source, "allowed_actions", ())),
    }


def ranking_presentation_dto(source, entries, *, role, student_id=None, faculty_id=None):
    if role == "student":
        if not student_id:
            raise PermissionError("student ranking presentation is limited to self")
    elif role in {"teacher", "admin"}:
        if not faculty_id or _value(source, "faculty_id") != faculty_id:
            raise PermissionError("presentation is outside actor organization scope")
    else:
        raise PermissionError("unsupported presentation role")
    visible = list(entries)
    if role == "student":
        visible = [row for row in visible if _value(row, "student_id") == student_id]
    payload = {
        "kind": "ranking_batch", "id": _value(source, "id"),
        "batch_id": _value(source, "id"),
        "version": _value(source, "version"), "status": _value(source, "status"),
        "scope": _value(source, "scope_definition", {}),
        "reason_code": _value(source, "stale_reason") or _value(source, "reason_code"),
        "generated_at": _time(_value(source, "created_at")),
        "published_at": _time(_value(source, "published_at")),
        "updated_at": _time(_value(source, "updated_at")),
        "allowed_actions": _actions("ranking_batch", role, _value(source, "allowed_actions", ())),
        "total_count": _value(source, "total_count", len(entries)),
        "entries": [{"student_id": _value(row, "student_id"),
                     "comprehensive_score": str(_value(row, "frozen_score")) if _value(row, "frozen_score") is not None else None,
                     "rank": _value(row, "rank"), "eligible": _value(row, "eligible"),
                     "reason_code": _value(row, "exclusion_reason"),
                     **({"score_basis": _value(row, "score_basis", [])}
                        if role in {"teacher", "admin"} else {})} for row in visible],
    }
    return payload


def cycle_policy_dto(policy):
    """Public read model for the single global active cycle policy."""
    return {
        "cycle_code": policy.cycle_code,
        "display_name": policy.display_name,
        "policy_version": policy.version,
        "status": policy.status,
        "eligible_award_start_date": policy.eligible_award_start_date.isoformat(),
        "eligible_award_end_date": policy.eligible_award_end_date.isoformat(),
        "boundary": policy.boundary,
        "activated_at": policy.activated_at.isoformat() + "Z" if policy.activated_at else None,
    }


def score_snapshot_dto(data):
    required = {"student_id", "year", "status", "base", "categories",
                "comprehensive_score", "formula", "rule_version_ids",
                "cycle_policy_version_ids", "input_digest", "updated_at", "entries"}
    missing = required - set(data)
    if missing:
        raise ValueError(f"score DTO missing fields: {sorted(missing)}")
    return {key: data[key] for key in sorted(required)} | {
        "snapshot_id": data.get("snapshot_id"),
        "snapshot_version": data.get("snapshot_version"),
    }


def ranking_batch_dto(batch, entries):
    return {
        "batch_id": batch.id, "year": batch.year, "status": batch.status,
        "version": batch.version, "scope": batch.scope_definition,
        "rule_version_ids": batch.rule_version_ids,
        "generated_at": batch.created_at.isoformat() + "Z",
        "published_at": batch.published_at.isoformat() + "Z" if batch.published_at else None,
        "stale_reason": batch.stale_reason,
        "entries": [{"student_id": row.student_id,
                     "comprehensive_score": str(row.frozen_score) if row.frozen_score is not None else None,
                     "rank": row.rank, "display_order": row.display_order,
                     "eligible": row.eligible, "exclusion_reason": row.exclusion_reason}
                    for row in entries],
    }
