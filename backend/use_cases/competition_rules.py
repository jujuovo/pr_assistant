"""Application services for validating and loading competition packages."""

import copy
import hashlib
import json

from sqlalchemy.exc import IntegrityError

from automation_models import utcnow
from domain.competition_rules import (
    COMPETITION_FACT_FIELDS, CompetitionPackageError, normalize_competition_facts,
    validate_competition_package,
)
from extensions import db
from material_models import MaterialRecord
from models import Student
from material_models import MaterialEvent
from use_cases.scoring import mark_draft_rankings_stale, rebuild_student_snapshot
from workflow_models import (
    CompetitionNotificationIntent, CompetitionRulePackage,
    CompetitionRulePackageCommand, CompetitionRulePackageRevision, ScoreEntry,
)


def _command_digest(payload):
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def copy_competition_package_draft(
    user, *, source_package_id, target_cycle, idempotency_key, fail_at=None
):
    """Deep-copy one published package into an independent target-cycle draft."""
    if user is None or user.role != "admin" or not user.faculty_id:
        raise CompetitionPackageError("administrator authorization required", code="forbidden")
    if not isinstance(source_package_id, int) or source_package_id < 1:
        raise CompetitionPackageError("source_package_id must be positive", code="invalid_command")
    if not isinstance(target_cycle, int) or not 2000 <= target_cycle <= 2100:
        raise CompetitionPackageError("target_cycle is invalid", code="invalid_command")
    if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128:
        raise CompetitionPackageError("idempotency_key is invalid", code="invalid_command")
    command_payload = {
        "source_package_id": source_package_id,
        "target_cycle": target_cycle,
    }
    digest = _command_digest(command_payload)
    previous = CompetitionRulePackageCommand.query.filter_by(
        command_type="copy", idempotency_key=idempotency_key
    ).one_or_none()
    if previous:
        if previous.request_digest != digest:
            raise CompetitionPackageError(
                "idempotency key was used with different payload",
                code="idempotency_conflict",
            )
        return db.session.get(CompetitionRulePackage, previous.package_id), False
    source = CompetitionRulePackage.query.filter_by(id=source_package_id).with_for_update().one_or_none()
    if source is None or source.status not in {"current", "retired"} or source.published_at is None:
        raise CompetitionPackageError("source package is not published", code="source_not_published")
    if source.cycle_code == target_cycle:
        raise CompetitionPackageError("target cycle must differ from source", code="invalid_target_cycle")
    existing = CompetitionRulePackage.query.filter_by(
        cycle_code=target_cycle, scope_key=source.scope_key, status="draft"
    ).order_by(CompetitionRulePackage.version.desc()).first()
    if existing:
        raise CompetitionPackageError("target cycle already has a draft", code="target_draft_exists")
    snapshot = copy.deepcopy(source.snapshot)
    snapshot["cycle_code"] = target_cycle
    snapshot["package_id"] = f"competition-{target_cycle}"
    source_summary = {
        "id": source.id, "package_id": source.package_id,
        "cycle_code": source.cycle_code, "version": source.version,
        "digest": source.digest,
    }
    draft = CompetitionRulePackage(
        package_id=snapshot["package_id"], cycle_code=target_cycle,
        scope_key=source.scope_key, version=1, draft_revision=1, status="draft",
        snapshot=snapshot, digest=CompetitionRulePackage.canonical_digest(snapshot),
        source_package_id=source.id, source_digest=source.digest,
        source_summary=source_summary, created_by=user.id, updated_by=user.id,
        created_at=utcnow(), updated_at=utcnow(),
    )
    db.session.add(draft); db.session.flush()
    db.session.add(CompetitionRulePackageRevision(
        package_id=draft.id, revision=1, snapshot=copy.deepcopy(snapshot),
        digest=draft.digest, created_by=user.id, created_at=utcnow(),
    ))
    if fail_at == "after_draft":
        raise RuntimeError("injected copy failure")
    result = {"package_id": draft.id, "draft_revision": draft.draft_revision,
              "target_cycle": target_cycle, "source_package_id": source.id}
    db.session.add(CompetitionRulePackageCommand(
        command_type="copy", idempotency_key=idempotency_key,
        request_digest=digest, package_id=draft.id, result=result,
        created_by=user.id, created_at=utcnow(),
    ))
    db.session.flush()
    return draft, True


def edit_competition_package_draft(
    user, package, *, expected_revision, snapshot, fail_at=None
):
    if user is None or user.role != "admin" or not user.faculty_id:
        raise CompetitionPackageError("administrator authorization required", code="forbidden")
    if package.status != "draft":
        raise CompetitionPackageError("published packages are immutable", code="package_immutable")
    if not isinstance(expected_revision, int) or expected_revision < 1:
        raise CompetitionPackageError("draft revision is invalid", code="invalid_command")
    if package.draft_revision != expected_revision:
        raise CompetitionPackageError("draft revision changed", code="version_conflict")
    if not isinstance(snapshot, dict):
        raise CompetitionPackageError("package snapshot must be an object", code="invalid_package")
    candidate = copy.deepcopy(snapshot)
    if candidate.get("cycle_code") != package.cycle_code:
        raise CompetitionPackageError("draft cycle cannot change", code="immutable_identity")
    if candidate.get("package_id") != package.package_id:
        raise CompetitionPackageError("draft package id cannot change", code="immutable_identity")
    digest = CompetitionRulePackage.canonical_digest(candidate)
    if digest == package.digest:
        return package, False
    package.snapshot = candidate
    package.digest = digest
    package.draft_revision += 1
    package.updated_by = user.id
    package.updated_at = utcnow()
    db.session.add(CompetitionRulePackageRevision(
        package_id=package.id, revision=package.draft_revision,
        snapshot=copy.deepcopy(candidate), digest=digest,
        created_by=user.id, created_at=package.updated_at,
    ))
    db.session.flush()
    if fail_at == "after_revision":
        raise RuntimeError("injected edit failure")
    return package, True


def _flatten(value, path=""):
    if isinstance(value, dict):
        result = {}
        for key in sorted(value):
            result.update(_flatten(value[key], f"{path}.{key}" if path else str(key)))
        return result
    if isinstance(value, list):
        return {path: copy.deepcopy(value)}
    return {path: value}


def _structured_changes(before, after, prefix):
    left, right = _flatten(before, prefix), _flatten(after, prefix)
    added = [{"path": path, "value": right[path]} for path in sorted(right.keys() - left.keys())]
    removed = [{"path": path, "value": left[path]} for path in sorted(left.keys() - right.keys())]
    changed = [{"path": path, "before": left[path], "after": right[path]}
               for path in sorted(left.keys() & right.keys()) if left[path] != right[path]]
    return added, removed, changed


def preview_competition_package_diff(user, package):
    """Read-only semantic diff against the draft's recorded source package."""
    if user is None or user.role != "admin" or not user.faculty_id:
        raise CompetitionPackageError("administrator authorization required", code="forbidden")
    if package.status != "draft" or package.source_package_id is None:
        raise CompetitionPackageError("draft has no source package", code="source_package_missing")
    source = db.session.get(CompetitionRulePackage, package.source_package_id)
    if source is None or source.digest != package.source_digest:
        raise CompetitionPackageError("source package identity changed", code="source_package_changed")
    old_catalog = {item["competition_id"]: item for item in source.snapshot.get("catalog", [])}
    new_catalog = {item["competition_id"]: item for item in package.snapshot.get("catalog", [])}
    added = [{"path": f"catalog.{key}", "value": new_catalog[key]}
             for key in sorted(new_catalog.keys() - old_catalog.keys())]
    removed = [{"path": f"catalog.{key}", "value": old_catalog[key]}
               for key in sorted(old_catalog.keys() - new_catalog.keys())]
    changed = []
    for key in sorted(old_catalog.keys() & new_catalog.keys()):
        a, r, c = _structured_changes(old_catalog[key], new_catalog[key], f"catalog.{key}")
        added.extend(a); removed.extend(r); changed.extend(c)
    for key in ("score_matrix", "field_schema", "policy", "evidence_period"):
        a, r, c = _structured_changes(
            source.snapshot.get(key, {}), package.snapshot.get(key, {}), key
        )
        added.extend(a); removed.extend(r); changed.extend(c)
    materials = MaterialRecord.query.filter_by(
        category="competition", year=package.cycle_code
    ).order_by(MaterialRecord.id).all()
    impacts = []
    for row in materials:
        facts = dict(row.confirmed_terms or row.data or {})
        facts = {key: value for key, value in facts.items() if key in COMPETITION_FACT_FIELDS}
        try:
            normalized = normalize_competition_facts(package.snapshot, facts)
            result = {"status": "matched", "competition_id": normalized["competition_id"],
                      "candidate_score": normalized["candidate_score"]}
        except CompetitionPackageError as error:
            result = {"status": "unmatched", "reason_code": error.code}
        impacts.append({"material_id": row.id, "student_id": row.student_id,
                        "status": row.status, "candidate": result})
    return {
        "source_package_id": source.id, "candidate_package_id": package.id,
        "source_digest": source.digest, "candidate_digest": package.digest,
        "draft_revision": package.draft_revision,
        "added": added, "removed": removed, "changed": changed,
        "material_impact": {"count": len(impacts), "items": impacts},
        "read_only": True,
    }


def publish_competition_package_draft(
    user, package, *, expected_revision, idempotency_key, fail_at=None
):
    if user is None or user.role != "admin" or not user.faculty_id:
        raise CompetitionPackageError("administrator authorization required", code="forbidden")
    request_value = {"package_id": package.id, "expected_revision": expected_revision}
    request_digest = _command_digest(request_value)
    previous = CompetitionRulePackageCommand.query.filter_by(
        command_type="publish", idempotency_key=idempotency_key
    ).one_or_none()
    if previous:
        if previous.request_digest != request_digest:
            raise CompetitionPackageError(
                "idempotency key was used with different payload", code="idempotency_conflict"
            )
        return db.session.get(CompetitionRulePackage, previous.package_id), False
    locked = CompetitionRulePackage.query.filter_by(id=package.id).with_for_update().one()
    if locked.status != "draft":
        raise CompetitionPackageError("only a draft can be published", code="package_immutable")
    if locked.draft_revision != expected_revision:
        raise CompetitionPackageError("draft revision changed", code="version_conflict")
    validated = validate_competition_package(locked.snapshot)
    if validated.cycle_code != locked.cycle_code or validated.package_id != locked.package_id:
        raise CompetitionPackageError("package identity does not match snapshot", code="invalid_package")
    current = CompetitionRulePackage.query.filter_by(
        cycle_code=locked.cycle_code, scope_key=locked.scope_key, status="current"
    ).with_for_update().one_or_none()
    if current is not None:
        raise CompetitionPackageError(
            "target cycle already has a current package", code="competition_package_already_current"
        )
    locked.status = "current"
    locked.current_scope_key = CompetitionRulePackage.current_key(
        locked.cycle_code, locked.scope_key
    )
    locked.published_by = user.id
    locked.published_at = locked.updated_at = utcnow()
    locked.updated_by = user.id
    db.session.flush()
    if fail_at == "after_publish":
        raise RuntimeError("injected publish failure")
    result = {"package_id": locked.id, "status": locked.status,
              "version": locked.version, "draft_revision": locked.draft_revision}
    db.session.add(CompetitionRulePackageCommand(
        command_type="publish", idempotency_key=idempotency_key,
        request_digest=request_digest, package_id=locked.id, result=result,
        created_by=user.id, created_at=utcnow(),
    ))
    try:
        db.session.flush()
    except IntegrityError as error:
        raise CompetitionPackageError(
            "package was published concurrently", code="competition_package_publish_conflict"
        ) from error
    return locked, True


def preview_competition_package_correction(actor, new_snapshot, *, scope_key="global"):
    """Return a deterministic, read-only impact report for a candidate package."""
    if actor is None or actor.role != "admin" or not actor.faculty_id:
        raise CompetitionPackageError("administrator authorization required", code="forbidden")
    validated = validate_competition_package(new_snapshot)
    current = CompetitionRulePackage.query.filter_by(
        cycle_code=validated.cycle_code, scope_key=scope_key, status="current"
    ).one_or_none()
    if current is None:
        raise CompetitionPackageError("current package not found", code="competition_package_missing")
    new_digest = CompetitionRulePackage.canonical_digest(new_snapshot)
    materials = MaterialRecord.query.filter_by(
        category="competition", year=validated.cycle_code,
        competition_rule_package_id=current.id,
    ).order_by(MaterialRecord.id).all()
    active_scores = {entry.material_record_id: entry for entry in ScoreEntry.query.filter(
        ScoreEntry.material_record_id.in_([row.id for row in materials]),
        ScoreEntry.status == "active",
    ).all()} if materials else {}
    impacts = []
    for row in materials:
        saved = dict(row.confirmed_terms or row.data or {})
        facts = {key: value for key, value in saved.items() if key in COMPETITION_FACT_FIELDS}
        old = normalize_competition_facts(current.snapshot, facts)
        try:
            new = normalize_competition_facts(new_snapshot, facts)
            new_match = {
                "status": "matched", "competition_id": new["competition_id"],
                "candidate_score": new["candidate_score"],
            }
            changed = (
                old["competition_id"] != new["competition_id"] or
                str(old["candidate_score"]) != str(new["candidate_score"])
            )
            reasons = (["candidate_score_changed"]
                       if str(old["candidate_score"]) != str(new["candidate_score"]) else [])
        except CompetitionPackageError as error:
            new_match = {"status": "unmatched", "code": error.code, "candidate_score": None}
            changed = True
            reasons = ["mapping_changed"]
        if changed:
            entry = active_scores.get(row.id)
            impacts.append({
                "material_id": row.id, "student_id": row.student_id,
                "material_version": row.version, "status": row.status,
                "old_match": {"status": "matched", "competition_id": old["competition_id"],
                              "candidate_score": old["candidate_score"]},
                "new_match": new_match, "reasons": reasons,
                "historical_score": ({"score_entry_id": entry.id,
                    "candidate_score": str(entry.candidate_score),
                    "effective_score": str(entry.effective_score),
                    "included": entry.included} if entry else None),
            })
    return {
        "cycle_code": validated.cycle_code, "scope_key": scope_key,
        "old_package": {"id": current.id, "package_id": current.package_id,
                        "version": current.version, "digest": current.digest},
        "new_package": {"package_id": new_snapshot["package_id"],
                        "version": current.version + 1, "digest": new_digest},
        "changed": new_digest != current.digest,
        "material_count": len(materials), "affected_count": len(impacts),
        "impacts": impacts,
    }


def switch_competition_package(actor, new_snapshot, *, scope_key="global", fail_at=None):
    report = preview_competition_package_correction(actor, new_snapshot, scope_key=scope_key)
    if not report["changed"]:
        raise CompetitionPackageError("corrected package is identical", code="competition_package_unchanged")
    old = CompetitionRulePackage.query.filter_by(
        cycle_code=report["cycle_code"], scope_key=scope_key, status="current"
    ).with_for_update().one()
    old.status = "retired"; old.current_scope_key = None; old.retired_at = utcnow()
    db.session.flush()
    if fail_at == "after_retire": raise RuntimeError("injected after_retire failure")
    new = CompetitionRulePackage(
        package_id=new_snapshot["package_id"], cycle_code=report["cycle_code"],
        scope_key=scope_key, version=old.version + 1, status="current",
        snapshot=new_snapshot, digest=report["new_package"]["digest"],
        current_scope_key=CompetitionRulePackage.current_key(report["cycle_code"], scope_key),
        created_by=actor.id, published_by=actor.id, published_at=utcnow(),
    )
    db.session.add(new); db.session.flush()
    if fail_at == "after_publish": raise RuntimeError("injected after_publish failure")
    affected_students = set()
    for impact in report["impacts"]:
        row = MaterialRecord.query.filter_by(id=impact["material_id"]).with_for_update().one()
        row.status = "rule_reconfirmation_required"
        row.version += 1
        row.competition_duplicate_digest = None
        db.session.add(MaterialEvent(record_id=row.id, actor_id=actor.id,
            action="competition_rule_invalidated", details={
                "old_package_id": old.id, "new_package_id": new.id,
                "old_material_version": impact["material_version"],
                "new_material_version": row.version, "reasons": impact["reasons"],
            }))
        db.session.add(CompetitionNotificationIntent(
            intent_key=f"rule-correction:{new.id}:{row.id}", student_id=row.student_id,
            material_record_id=row.id, event_type="competition_rule_reconfirmation_required",
            payload={"material_id": row.id, "new_package_id": new.id,
                     "material_version": row.version},
        ))
        entries = ScoreEntry.query.filter_by(material_record_id=row.id, status="active").with_for_update().all()
        for entry in entries:
            entry.status = "invalidated"; entry.included = False
            entry.exclusion_reason = "rule_package_corrected"
            entry.invalidated_reason = "competition rule package corrected; student reconfirmation required"
            entry.invalidated_at = entry.updated_at = utcnow()
        affected_students.add((row.student_id, row.year))
    if fail_at == "after_invalidation": raise RuntimeError("injected after_invalidation failure")
    snapshots, stale_ids = [], []
    for student_id, year in sorted(affected_students):
        snapshot, _ = rebuild_student_snapshot(student_id, year)
        snapshots.append(snapshot.id)
        student = Student.query.filter_by(student_id=student_id).one()
        stale_ids.extend(batch.id for batch in mark_draft_rankings_stale(
            student, year, "competition rule package corrected"
        ))
    if fail_at == "after_snapshot": raise RuntimeError("injected after_snapshot failure")
    return {**report, "old_package_id": old.id, "new_package_id": new.id,
            "snapshot_ids": snapshots, "stale_ranking_batch_ids": sorted(set(stale_ids))}


def send_competition_notification(intent_id, sender):
    intent = CompetitionNotificationIntent.query.filter_by(id=intent_id).with_for_update().one()
    if intent.status == "sent":
        return {"intent_id": intent.id, "status": "sent", "replayed": True}
    intent.attempts += 1
    intent.updated_at = utcnow()
    try:
        sender(intent.student_id, intent.event_type, dict(intent.payload))
    except Exception as error:
        intent.last_error = str(error)[:1000]
        db.session.flush()
        return {"intent_id": intent.id, "status": "pending", "replayed": False,
                "attempts": intent.attempts, "error": intent.last_error}
    intent.status = "sent"; intent.sent_at = utcnow(); intent.last_error = None
    db.session.flush()
    return {"intent_id": intent.id, "status": "sent", "replayed": False,
            "attempts": intent.attempts}


def load_current_competition_package(actor, snapshot, *, scope_key="global"):
    validated = validate_competition_package(snapshot)
    digest = CompetitionRulePackage.canonical_digest(snapshot)
    existing = CompetitionRulePackage.query.filter_by(
        cycle_code=validated.cycle_code,
        scope_key=scope_key,
        digest=digest,
    ).one_or_none()
    if existing is not None:
        return existing, False

    current = CompetitionRulePackage.query.filter_by(
        cycle_code=validated.cycle_code,
        scope_key=scope_key,
        status="current",
    ).one_or_none()
    if current is not None:
        raise CompetitionPackageError(
            "a different current package already exists",
            code="competition_package_already_current",
        )

    package = CompetitionRulePackage(
        package_id=validated.package_id,
        cycle_code=validated.cycle_code,
        scope_key=scope_key,
        version=1,
        status="current",
        snapshot=snapshot,
        digest=digest,
        current_scope_key=CompetitionRulePackage.current_key(
            validated.cycle_code, scope_key
        ),
        created_by=actor.id,
        published_by=actor.id,
        published_at=utcnow(),
    )
    db.session.add(package)
    try:
        db.session.flush()
    except IntegrityError as error:
        raise CompetitionPackageError(
            "a current package was published concurrently",
            code="competition_package_publish_conflict",
        ) from error
    return package, True
