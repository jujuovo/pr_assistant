"""Scoring and student score snapshot application use cases."""

import hashlib
import json
from datetime import datetime

from sqlalchemy import or_

from automation_models import utcnow
from domain.scoring import (
    ScoreCandidate,
    ScoreFact,
    allocate_candidates,
    build_score_projection,
    calculate_score,
)
from extensions import db
from models import FacultyScoreSettings, Rule, Student
from workflow_models import (MaterialReviewCommand, RankingBatch, RuleVersion, ScoreEntry,
                             ScoreOverrideAudit, ScoreRecalculationCommand,
                             StudentScoreSnapshot)
from material_models import MaterialRecord


class ScoringUseCaseError(ValueError):
    def __init__(self, message, *, status_code=404, code="score_snapshot_not_found"):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class _ScoreRecalculationAbort(RuntimeError):
    pass


def _legacy_application_year(application):
    if application.cycle_code is not None:
        return application.cycle_code
    raise ScoringUseCaseError("application has no fixed recommendation cycle")


def adapt_legacy_application(application, *, year=None, source_type="legacy_application",
                             source_revision=None, rule_version_id=None):
    """Idempotently project one approved legacy Application into ScoreEntry.

    The historical final score is preserved as the authoritative reviewed value;
    the bound immutable rule version provides provenance rather than recalculation.
    """
    if application.status != "approved":
        return {
            "status": "skipped",
            "reason": "application_not_approved",
            "application_id": application.id,
        }
    if application.final_score is None:
        return {
            "status": "skipped",
            "reason": "approved_application_missing_final_score",
            "application_id": application.id,
        }
    if application.rule_id is None:
        return {
            "status": "needs_rule",
            "reason": "application_has_no_rule",
            "application_id": application.id,
        }

    if rule_version_id is not None:
        version = db.session.get(RuleVersion, rule_version_id)
        if version is None or version.status != "published" or version.rule_id != application.rule_id:
            raise ScoringUseCaseError("explicit rule version is not applicable to application")
    else:
        version = (
            RuleVersion.query.filter_by(rule_id=application.rule_id, status="published")
            .order_by(RuleVersion.version.desc(), RuleVersion.id.desc()).first()
        )
    if version is None:
        return {
            "status": "needs_rule",
            "reason": "no_published_rule_version",
            "application_id": application.id,
        }
    rule = db.session.get(Rule, application.rule_id)
    if rule is None:
        return {
            "status": "needs_rule",
            "reason": "rule_not_found",
            "application_id": application.id,
        }
    if rule.sub_type == "competition":
        return {
            "status": "skipped",
            "reason": "competition_requires_material_record",
            "application_id": application.id,
        }

    if source_revision is None:
        previous = ScoreEntry.query.filter_by(source_type=source_type, source_id=str(application.id)).order_by(ScoreEntry.source_revision.desc()).first()
        if previous and previous.status == "active" and previous.rule_version_id == version.id and previous.effective_score == application.final_score:
            snapshot = StudentScoreSnapshot.query.filter_by(student_id=previous.student_id, year=previous.year, status="current").first()
            return {"status": "scored", "application_id": application.id, "score_entry_id": previous.id,
                    "snapshot_id": snapshot.id if snapshot else None, "replayed": True}
        source_revision = (previous.source_revision + 1) if previous else 1
        if previous and previous.status == "active":
            previous.status, previous.included = "invalidated", False
            previous.exclusion_reason = "source_superseded"
            previous.invalidated_reason = "legacy source score changed"
            previous.invalidated_at = previous.updated_at = utcnow()
    idempotency_key = (
        f"{source_type}:{application.id}:{source_revision}:rule:{version.id}"
    )
    existing = ScoreEntry.query.filter_by(idempotency_key=idempotency_key).first()
    effective_year = year if year is not None else _legacy_application_year(application)
    if existing is not None:
        snapshot = StudentScoreSnapshot.query.filter_by(
            student_id=existing.student_id, year=existing.year, status="current"
        ).first()
        return {
            "status": "scored",
            "application_id": application.id,
            "score_entry_id": existing.id,
            "snapshot_id": snapshot.id if snapshot else None,
            "replayed": True,
        }

    student = Student.query.filter_by(student_id=application.student_id).first()
    if student is None:
        raise ScoringUseCaseError("legacy application student not found")
    faculty_id = application.faculty_id or student.faculty_id
    if faculty_id is None:
        raise ScoringUseCaseError("legacy application has no faculty")

    entry = ScoreEntry(
        student_id=application.student_id,
        faculty_id=faculty_id,
        year=effective_year,
        cycle_policy_version_id=application.cycle_policy_version_id,
        score_group=application.application_type,
        category=rule.sub_type or "legacy",
        source_type=source_type,
        source_id=str(application.id),
        source_revision=source_revision,
        material_record_id=None,
        rule_version_id=version.id,
        raw_score=application.final_score,
        adjusted_score=application.final_score,
        effective_score=application.final_score,
        included=True,
        status="active",
        idempotency_key=idempotency_key,
    )
    db.session.add(entry)
    db.session.flush()
    snapshot, _created = rebuild_student_snapshot(application.student_id, effective_year)
    stale = mark_draft_rankings_stale(
        student,
        effective_year,
        f"legacy application imported for {application.student_id}",
    )
    return {
        "status": "scored",
        "application_id": application.id,
        "score_entry_id": entry.id,
        "snapshot_id": snapshot.id,
        "stale_ranking_batch_ids": [batch.id for batch in stale],
        "replayed": False,
    }


def _active_entries(student_id, year):
    return (
        ScoreEntry.query.filter_by(student_id=student_id, year=year, status="active")
        .order_by(ScoreEntry.id)
        .all()
    )


def rebuild_student_snapshot(student_id, year):
    student = Student.query.filter_by(student_id=student_id).with_for_update().first()
    if not student:
        raise ScoringUseCaseError("student not found")
    entries = _active_entries(student_id, year)
    legacy_rule_ids = {entry.rule_version_id for entry in entries if entry.rule_version_id is not None}
    versions = {
        version.id: version
        for version in RuleVersion.query.filter(
            RuleVersion.id.in_(legacy_rule_ids)
        ).all()
    } if legacy_rule_ids else {}
    candidates = []
    for entry in entries:
        if entry.competition_rule_package_id is not None:
            continue
        version = versions.get(entry.rule_version_id)
        if not version:
            raise ScoringUseCaseError("score entry references a missing rule version")
        max_count = version.snapshot.get("max_count")
        if max_count is not None:
            max_count = int(max_count)
        candidates.append(
            ScoreCandidate(
                entry_id=entry.id,
                rule_version_id=entry.rule_version_id,
                semantic_key=f"{entry.source_type}:{entry.source_id}",
                effective_score=entry.effective_score,
                max_count=max_count,
            )
        )
    allocation = {item.entry_id: item for item in allocate_candidates(candidates)}
    for entry in entries:
        if entry.competition_rule_package_id is not None:
            continue
        choice = allocation[entry.id]
        entry.included = choice.included
        entry.exclusion_reason = choice.reason
        entry.updated_at = utcnow()

    settings = FacultyScoreSettings.query.filter_by(faculty_id=student.faculty_id).first()
    weight = settings.academic_score_weight if settings else 80
    specialty_max = settings.specialty_max_score if settings else 15
    performance_max = settings.performance_max_score if settings else 5
    projection = build_score_projection(
        student.academic_score,
        [
            ScoreFact(
                entry.id,
                entry.score_group,
                entry.effective_score,
                (entry.rule_version_id if entry.rule_version_id is not None
                 else -entry.competition_rule_package_id),
                included=entry.included,
                status=entry.status,
            )
            for entry in entries
        ],
        academic_weight=weight,
        specialty_max=specialty_max,
        performance_max=performance_max,
    )
    # Compatibility projection only; the snapshot and score facts remain authoritative.
    student.academic_specialty_total = float(projection.specialty_score)
    student.comprehensive_performance_total = float(projection.performance_score)
    student.comprehensive_score = float(projection.comprehensive_score)
    current = StudentScoreSnapshot.query.filter_by(
        student_id=student_id, year=year, status="current"
    ).order_by(StudentScoreSnapshot.version.desc()).first()
    if current and current.input_digest == projection.input_digest:
        return current, False
    next_version = (current.version + 1) if current else 1
    if current:
        current.status = "superseded"
        current.updated_at = utcnow()
    snapshot = StudentScoreSnapshot(
        student_id=student.student_id,
        faculty_id=student.faculty_id,
        year=year,
        version=next_version,
        status="current",
        academic_base_score=projection.academic_base_score,
        academic_weight=projection.academic_weight,
        specialty_raw_score=projection.specialty_raw_score,
        specialty_score=projection.specialty_score,
        performance_raw_score=projection.performance_raw_score,
        performance_score=projection.performance_score,
        comprehensive_score=projection.comprehensive_score,
        input_digest=projection.input_digest,
        rule_version_ids=list(projection.rule_version_ids),
        breakdown=list(projection.breakdown),
    )
    db.session.add(snapshot)
    db.session.flush()
    return snapshot, True


def invalidate_score_entries(source_type, source_id, reason):
    if not isinstance(reason, str) or not reason.strip():
        raise ScoringUseCaseError("invalidation reason is required")
    entries = ScoreEntry.query.filter_by(
        source_type=source_type, source_id=str(source_id), status="active"
    ).with_for_update().all()
    affected = set()
    for entry in entries:
        entry.status = "invalidated"
        entry.included = False
        entry.exclusion_reason = "source_invalidated"
        entry.invalidated_reason = reason.strip()
        entry.invalidated_at = utcnow()
        entry.updated_at = utcnow()
        affected.add((entry.student_id, entry.year))
    snapshots = []
    for student_id, year in sorted(affected):
        snapshots.append(rebuild_student_snapshot(student_id, year)[0])
    return entries, snapshots


def match_published_rule(row, cycle_code=None):
    """Resolve one rule for fixed cycle/category/faculty without arbitrary ties."""
    candidates = (
        db.session.query(RuleVersion, Rule)
        .join(Rule, Rule.id == RuleVersion.rule_id)
        .filter(
            RuleVersion.status == "published",
            Rule.status == "active",
        )
        .all()
    )
    candidates = [
        pair
        for pair in candidates
        if pair[0].snapshot.get("cycle_code") == (cycle_code or row.year)
        and pair[0].snapshot.get("sub_type") == row.category
        and pair[1].sub_type == row.category
        and pair[0].snapshot.get("faculty_id") in (None, row.faculty_id)
        and pair[1].faculty_id in (None, row.faculty_id)
    ]
    if not candidates:
        return {"status": "no_match", "reason": "no_applicable_published_rule"}
    latest_by_rule = {}
    for version, rule in candidates:
        previous = latest_by_rule.get(rule.id)
        if previous is None or version.version > previous[0].version:
            latest_by_rule[rule.id] = (version, rule)
    candidates = list(latest_by_rule.values())
    exact = [pair for pair in candidates if pair[0].snapshot.get("faculty_id") == row.faculty_id]
    if exact:
        candidates = exact
    if len(candidates) != 1:
        return {
            "status": "ambiguous",
            "reason": "ambiguous_published_rules",
            "rule_version_ids": sorted(version.id for version, _rule in candidates),
        }
    version, rule = candidates[0]
    return {"status": "matched", "version": version, "rule": rule}


def mark_draft_rankings_stale(student, year, reason):
    query = RankingBatch.query.filter_by(
        year=year, faculty_id=student.faculty_id, status="draft"
    )
    batches = query.all()
    changed = []
    for batch in batches:
        if batch.major_id is not None and batch.major_id != student.major_id:
            continue
        batch.status = "stale"
        batch.stale_reason = reason
        batch.version += 1
        batch.updated_at = utcnow()
        changed.append(batch)
    return changed


def score_verified_material(row, review_key, *, actor=None, override_score=None,
                            override_reason=None):
    """Create the score fact and projections for one verified material."""
    if row.rule_version_id is not None:
        version = db.session.get(RuleVersion, row.rule_version_id)
        rule = db.session.get(Rule, version.rule_id) if version else None
        if not version or version.status != "published" or not rule:
            return {"status": "needs_rule", "reason": "fixed_rule_version_unavailable",
                    "rule_version_ids": [row.rule_version_id]}
    else:
        match = match_published_rule(row)
        if match["status"] != "matched":
            return {"status": "needs_rule", "reason": match["reason"],
                    "rule_version_ids": match.get("rule_version_ids", [])}
        version, rule = match["version"], match["rule"]
    calculation = calculate_score(version.snapshot)
    effective_score = calculation.effective_score
    if override_score is not None:
        from decimal import Decimal, InvalidOperation
        try:
            override = Decimal(str(override_score))
        except InvalidOperation:
            raise ScoringUseCaseError("人工改写分数必须为有限非负数") from None
        maximum = version.snapshot.get("max_score")
        if (not override.is_finite() or override < 0 or
                (maximum is not None and override > Decimal(str(maximum)))):
            raise ScoringUseCaseError("人工改写分数超出规则单项上限")
        if not actor or actor.role not in {"teacher", "admin"}:
            raise ScoringUseCaseError("没有人工改写权限")
        if not isinstance(override_reason, str) or not override_reason.strip():
            raise ScoringUseCaseError("人工改写必须填写理由")
        if len(override_reason.strip()) > 1000:
            raise ScoringUseCaseError("人工改写理由不能超过1000字符")
        effective_score = override
    idempotency_key = f"material:{row.id}:{row.version}:rule:{version.id}:{review_key}"
    existing = ScoreEntry.query.filter_by(idempotency_key=idempotency_key).first()
    if existing:
        snapshot = StudentScoreSnapshot.query.filter_by(
            student_id=row.student_id, year=row.year, status="current"
        ).first()
        return {
            "status": "scored",
            "score_entry_id": existing.id,
            "snapshot_id": snapshot.id if snapshot else None,
            "replayed": True,
        }
    entry = ScoreEntry(
        student_id=row.student_id,
        faculty_id=row.faculty_id,
        year=row.year,
        cycle_policy_version_id=row.cycle_policy_version_id,
        score_group=rule.type,
        category=row.category,
        source_type="material",
        source_id=str(row.id),
        source_revision=row.version,
        material_record_id=row.id,
        rule_version_id=version.id,
        raw_score=calculation.raw_score,
        adjusted_score=calculation.adjusted_score,
        effective_score=effective_score,
        included=True,
        status="active",
        idempotency_key=idempotency_key,
    )
    db.session.add(entry)
    db.session.flush()
    if override_score is not None:
        db.session.add(ScoreOverrideAudit(
            score_entry_id=entry.id, source_type="material", source_id=str(row.id),
            source_version=row.version, rule_version_id=version.id,
            automatic_score=calculation.effective_score,
            override_score=effective_score,
            difference=effective_score - calculation.effective_score,
            reason=override_reason.strip(), actor_id=actor.id,
        ))
    snapshot, _created = rebuild_student_snapshot(row.student_id, row.year)
    student = Student.query.filter_by(student_id=row.student_id).one()
    if row.application_id:
        from models import Application
        application = db.session.get(Application, row.application_id)
        if application:
            application.status = "approved"
            application.final_score = float(effective_score)
            application.rule_id = rule.id
    stale = mark_draft_rankings_stale(
        student, row.year, f"score snapshot changed for {row.student_id}"
    )
    return {
        "status": "scored",
        "score_entry_id": entry.id,
        "snapshot_id": snapshot.id,
        "automatic_score": str(calculation.effective_score),
        "override_score": str(effective_score) if override_score is not None else None,
        "effective_score": str(effective_score),
        "stale_ranking_batch_ids": [batch.id for batch in stale],
        "replayed": False,
    }


def preview_student_score(student, year):
    entries = _active_entries(student.student_id, year)
    versions = {
        version.id: version
        for version in RuleVersion.query.filter(
            RuleVersion.id.in_({entry.rule_version_id for entry in entries})
        ).all()
    } if entries else {}
    candidates = []
    for entry in entries:
        version = versions.get(entry.rule_version_id)
        if not version:
            raise ScoringUseCaseError("score entry references a missing rule version")
        max_count = version.snapshot.get("max_count")
        candidates.append(
            ScoreCandidate(
                entry.id,
                entry.rule_version_id,
                f"{entry.source_type}:{entry.source_id}",
                entry.effective_score,
                int(max_count) if max_count is not None else None,
            )
        )
    choices = {item.entry_id: item for item in allocate_candidates(candidates)}
    settings = FacultyScoreSettings.query.filter_by(faculty_id=student.faculty_id).first()
    return build_score_projection(
        student.academic_score,
        [
            ScoreFact(
                entry.id,
                entry.score_group,
                entry.effective_score,
                entry.rule_version_id,
                included=choices[entry.id].included,
                status=entry.status,
            )
            for entry in entries
        ],
        academic_weight=settings.academic_score_weight if settings else 80,
        specialty_max=settings.specialty_max_score if settings else 15,
        performance_max=settings.performance_max_score if settings else 5,
    )


def recalculate_score_snapshots(
    year,
    *,
    student_id=None,
    faculty_id=None,
    major_id=None,
    rule_version_id=None,
    preview=False,
):
    query = Student.query.order_by(Student.student_id)
    if student_id:
        query = query.filter_by(student_id=student_id)
    if faculty_id:
        query = query.filter_by(faculty_id=faculty_id)
    if major_id:
        query = query.filter_by(major_id=major_id)
    if rule_version_id:
        ids = db.session.query(ScoreEntry.student_id).filter_by(
            year=year, rule_version_id=rule_version_id
        )
        query = query.filter(Student.student_id.in_(ids))
    students = query.all()
    results, errors = [], []
    changed_student_ids = []
    unchanged_student_ids = []
    for student in students:
        try:
            if preview:
                projection = preview_student_score(student, year)
                current = StudentScoreSnapshot.query.filter_by(
                    student_id=student.student_id, year=year, status="current"
                ).order_by(StudentScoreSnapshot.version.desc()).first()
                changed = current is None or current.input_digest != projection.input_digest
                (changed_student_ids if changed else unchanged_student_ids).append(
                    student.student_id
                )
                results.append({
                    "student_id": student.student_id,
                    "input_digest": projection.input_digest,
                    "comprehensive_score": str(projection.comprehensive_score),
                    "current_snapshot_id": current.id if current else None,
                    "current_snapshot_version": current.version if current else None,
                    "current_input_digest": current.input_digest if current else None,
                    "current_comprehensive_score": (
                        str(current.comprehensive_score) if current else None
                    ),
                    "change_type": "create" if current is None else (
                        "update" if changed else "unchanged"
                    ),
                    "changed": changed,
                    "created": False,
                    "preview": True,
                })
            else:
                snapshot, created = rebuild_student_snapshot(student.student_id, year)
                results.append({
                    "student_id": student.student_id,
                    "snapshot_id": snapshot.id,
                    "input_digest": snapshot.input_digest,
                    "comprehensive_score": str(snapshot.comprehensive_score),
                    "created": created,
                    "preview": False,
                })
        except Exception as error:
            errors.append({
                "student_id": student.student_id,
                "error": str(error),
                "error_type": type(error).__name__,
            })
    response = {
        "year": year,
        "preview": preview,
        "results": results,
        "errors": errors,
        "complete": not errors,
    }
    if preview:
        selected_ids = set(changed_student_ids)
        affected_batches = []
        for batch in RankingBatch.query.filter_by(
            year=year, faculty_id=faculty_id, status="draft"
        ).order_by(RankingBatch.id).all():
            if batch.major_id is not None and not any(
                student.student_id in selected_ids and student.major_id == batch.major_id
                for student in students
            ):
                continue
            if not selected_ids:
                continue
            affected_batches.append({
                "batch_id": batch.id,
                "version": batch.version,
                "status": batch.status,
                "scope_type": batch.scope_type,
                "faculty_id": batch.faculty_id,
                "major_id": batch.major_id,
            })
        scope = {
            "year": year,
            "faculty_id": faculty_id,
            "major_id": major_id,
            "student_id": student_id,
            "rule_version_id": rule_version_id,
        }
        digest_payload = {
            "scope": scope,
            "inputs": sorted(
                (item["student_id"], item["input_digest"]) for item in results
            ),
            "failures": sorted(
                (item["student_id"], item["error_type"], item["error"])
                for item in errors
            ),
            "ranking_batches": [item["batch_id"] for item in affected_batches],
        }
        response.update({
            "preview_digest": hashlib.sha256(json.dumps(
                digest_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")).hexdigest(),
            "scope": scope,
            "input_summary": {
                "student_count": len(students),
                "successful_count": len(results),
                "failed_count": len(errors),
                "current_snapshot_count": sum(
                    item["current_snapshot_id"] is not None for item in results
                ),
            },
            "expected_changes": {
                "changed_count": len(changed_student_ids),
                "unchanged_count": len(unchanged_student_ids),
                "changed_student_ids": changed_student_ids,
                "unchanged_student_ids": unchanged_student_ids,
            },
            "failed_objects": errors,
            "affected_draft_rankings": affected_batches,
        })
    return response


def execute_score_recalculation(actor, *, scope, preview_digest, preview_expires_at,
                                idempotency_key):
    """Atomically rebuild a scope after proving its read-only preview is current."""
    if actor.role != "admin" or not actor.faculty_id:
        raise ScoringUseCaseError("only an authorized administrator may recalculate scores",
                                  status_code=403, code="forbidden")
    if not isinstance(scope, dict) or scope.get("faculty_id") != actor.faculty_id:
        raise ScoringUseCaseError("recalculation scope is outside administrator faculty",
                                  status_code=403, code="forbidden")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ScoringUseCaseError("idempotency_key is required", status_code=400,
                                  code="invalid_request")
    if not isinstance(preview_digest, str) or len(preview_digest) != 64:
        raise ScoringUseCaseError("valid preview_digest is required", status_code=400,
                                  code="invalid_request")
    try:
        expires_at = datetime.fromisoformat(preview_expires_at.replace("Z", "+00:00"))
        now = datetime.now(expires_at.tzinfo) if expires_at.tzinfo else utcnow()
    except (AttributeError, TypeError, ValueError) as error:
        raise ScoringUseCaseError("valid preview_expires_at is required", status_code=400,
                                  code="invalid_request") from error
    if expires_at <= now:
        raise ScoringUseCaseError("score recalculation preview has expired", status_code=409,
                                  code="preview_expired")
    request_payload = {"scope": scope, "preview_digest": preview_digest,
                       "preview_expires_at": preview_expires_at}
    request_digest = hashlib.sha256(json.dumps(
        request_payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    existing = ScoreRecalculationCommand.query.filter_by(
        idempotency_key=idempotency_key.strip()
    ).first()
    if existing:
        if existing.request_digest != request_digest:
            raise ScoringUseCaseError("idempotency key was already used with another request",
                                      status_code=409, code="idempotency_conflict")
        replay = dict(existing.result); replay["replayed"] = True
        return replay
    preview = recalculate_score_snapshots(
        scope.get("year"), student_id=scope.get("student_id"),
        faculty_id=scope.get("faculty_id"), major_id=scope.get("major_id"),
        rule_version_id=scope.get("rule_version_id"), preview=True,
    )
    if not preview["complete"]:
        raise ScoringUseCaseError("score recalculation preview contains failed objects",
                                  status_code=409, code="preview_blocked")
    if preview["preview_digest"] != preview_digest:
        raise ScoringUseCaseError("score recalculation preview is stale", status_code=409,
                                  code="preview_stale")
    object_results, stale_batches, failed_objects = [], {}, []
    try:
        with db.session.begin_nested():
            for item in preview["results"]:
                try:
                    snapshot, created = rebuild_student_snapshot(
                        item["student_id"], scope["year"]
                    )
                except Exception as error:
                    failed_objects.append({"student_id": item["student_id"],
                        "status": "failed", "error": str(error),
                        "error_type": type(error).__name__})
                    raise _ScoreRecalculationAbort from error
                student = Student.query.filter_by(student_id=item["student_id"]).one()
                batches = mark_draft_rankings_stale(
                    student, scope["year"], f"score recalculation command {idempotency_key.strip()}"
                ) if created else []
                for batch in batches:
                    stale_batches[batch.id] = batch
                object_results.append({"student_id": item["student_id"],
                    "status": "succeeded", "snapshot_id": snapshot.id,
                    "snapshot_version": snapshot.version, "created": created})
            result = {"status": "succeeded", "complete": True, "replayed": False,
                "preview_digest": preview_digest, "scope": scope,
                "objects": object_results, "failed_objects": [],
                "stale_ranking_batch_ids": sorted(stale_batches)}
            db.session.add(ScoreRecalculationCommand(
                idempotency_key=idempotency_key.strip(), request_digest=request_digest,
                preview_digest=preview_digest, scope=scope, status="succeeded",
                result=result, created_by=actor.id))
            db.session.flush()
    except _ScoreRecalculationAbort:
        rolled_back = [dict(item, status="rolled_back", snapshot_id=None)
                       for item in object_results]
        result = {"status": "failed", "complete": False, "replayed": False,
            "preview_digest": preview_digest, "scope": scope,
            "objects": rolled_back, "failed_objects": failed_objects,
            "stale_ranking_batch_ids": []}
        db.session.add(ScoreRecalculationCommand(
            idempotency_key=idempotency_key.strip(), request_digest=request_digest,
            preview_digest=preview_digest, scope=scope, status="failed",
            result=result, created_by=actor.id))
        db.session.flush()
    return result


def explain_student_score(student_id, year):
    snapshot = StudentScoreSnapshot.query.filter_by(
        student_id=student_id, year=year, status="current"
    ).order_by(StudentScoreSnapshot.version.desc()).first()
    entries = ScoreEntry.query.filter_by(student_id=student_id, year=year).order_by(
        ScoreEntry.id
    ).all()
    entry_by_material = {
        entry.material_record_id: entry for entry in entries if entry.material_record_id
    }
    audits = {
        audit.score_entry_id: audit
        for audit in ScoreOverrideAudit.query.filter(
            ScoreOverrideAudit.score_entry_id.in_([entry.id for entry in entries])
        ).all()
    } if entries else {}
    commands = (
        MaterialReviewCommand.query.join(
            MaterialRecord, MaterialReviewCommand.record_id == MaterialRecord.id
        ).filter(MaterialRecord.student_id == student_id, MaterialRecord.year == year)
        .order_by(MaterialReviewCommand.id).all()
    )
    latest_command = {command.record_id: command for command in commands}

    explained_entries = []
    represented_entry_ids = set()
    for record_id, command in latest_command.items():
        record = db.session.get(MaterialRecord, record_id)
        result = command.result.get("scoring", {})
        entry = entry_by_material.get(record_id)
        audit = audits.get(entry.id) if entry else None
        if entry:
            represented_entry_ids.add(entry.id)
        score = result.get("score") or result.get("scoring") or {}
        automatic = audit.automatic_score if audit else (
            entry.adjusted_score if entry else score.get("automatic_score")
        )
        override = audit.override_score if audit else score.get("override_score")
        candidate = entry.effective_score if entry else score.get("effective_score")
        explained_entries.append({
            "id": entry.id if entry else None,
            "project_source": {"type": "material", "id": str(record_id),
                               "category": record.category},
            "verification_status": result.get("verification_status"),
            "scoring_status": result.get("scoring_status"),
            "cycle_code": year,
            "cycle_policy_version_id": record.cycle_policy_version_id,
            "rule_version_id": entry.rule_version_id if entry else score.get("rule_version_id"),
            "automatic_score": str(automatic) if automatic is not None else None,
            "override_score": str(override) if override is not None else None,
            "candidate_score": str(candidate) if candidate is not None else None,
            "included_score": str(entry.effective_score if entry and entry.included else 0),
            "included": entry.included if entry else False,
            "exclusion_reason": (entry.exclusion_reason if entry else None)
                                or (result.get("eligibility") or {}).get("reason"),
            "allowed_actions": result.get("allowed_actions", []),
            "updated_at": (entry.updated_at if entry else command.created_at).isoformat() + "Z",
        })
    for entry in entries:
        if entry.id in represented_entry_ids:
            continue
        audit = audits.get(entry.id)
        explained_entries.append({
            "id": entry.id,
            "project_source": {"type": entry.source_type, "id": entry.source_id,
                               "category": entry.category},
            "verification_status": "verified",
            "scoring_status": "scored",
            "cycle_code": entry.year,
            "cycle_policy_version_id": entry.cycle_policy_version_id,
            "rule_version_id": entry.rule_version_id,
            "automatic_score": str(audit.automatic_score if audit else entry.adjusted_score),
            "override_score": str(audit.override_score) if audit else None,
            "candidate_score": str(entry.effective_score),
            "included_score": str(entry.effective_score if entry.included else 0),
            "included": entry.included,
            "exclusion_reason": entry.exclusion_reason,
            "allowed_actions": [],
            "updated_at": entry.updated_at.isoformat() + "Z",
        })
    represented_material_ids = {
        int(item["project_source"]["id"])
        for item in explained_entries
        if item["project_source"]["type"] == "material"
    }
    pending_materials = MaterialRecord.query.filter(
        MaterialRecord.student_id == student_id,
        MaterialRecord.status.in_(("rule_unmatched", "rule_available")),
        or_(MaterialRecord.cycle_policy_version_id.is_(None), MaterialRecord.year == year),
    ).order_by(MaterialRecord.id).all()
    for record in pending_materials:
        if record.id in represented_material_ids:
            continue
        unmatched = record.status == "rule_unmatched"
        candidate = None
        if not unmatched:
            from use_cases.materials import match_material_rule
            rule_match = match_material_rule(record, year)
            if rule_match["status"] == "matched":
                candidate = rule_match["match"]
        explained_entries.append({
            "id": None,
            "score_entry_id": None,
            "project_source": {"type": "material", "id": str(record.id),
                               "category": record.category},
            "verification_status": "unreviewed",
            "scoring_status": record.status,
            "cycle_code": year,
            "cycle_policy_version_id": record.cycle_policy_version_id,
            "rule_version_id": candidate["version_id"] if candidate else None,
            "source_version": record.version,
            "automatic_score": None,
            "override_score": None,
            "candidate_score": (str(candidate.get("score")) if candidate else None),
            "included_score": "0",
            "included": False,
            "exclusion_reason": ("材料词条没有对应计分" if unmatched
                                 else "规则已可用，等待学生确认"),
            "allowed_actions": (["edit", "view"] if unmatched
                                else ["confirm_submit", "edit", "view"]),
            "updated_at": record.updated_at.isoformat() + "Z",
        })
    if snapshot is None:
        latest_update = max(
            (item["updated_at"] for item in explained_entries), default=None
        )
        return {
            "student_id": student_id, "year": year,
            "snapshot_id": None, "snapshot_version": None,
            "status": "no_authoritative_snapshot",
            "base": {"academic_score": None, "academic_weight": None},
            "categories": {
                "academic": {"raw_score": None, "effective_score": None},
                "comprehensive": {"raw_score": None, "effective_score": None},
            },
            "comprehensive_score": None,
            "formula": None,
            "rule_version_ids": [], "cycle_policy_version_ids": [],
            "input_digest": None, "updated_at": latest_update,
            "entries": explained_entries,
        }
    return {
        "student_id": student_id,
        "year": year,
        "snapshot_id": snapshot.id,
        "snapshot_version": snapshot.version,
        "status": snapshot.status,
        "base": {
            "academic_score": str(snapshot.academic_base_score),
            "academic_weight": str(snapshot.academic_weight),
        },
        "categories": {
            "academic": {
                "raw_score": str(snapshot.specialty_raw_score),
                "effective_score": str(snapshot.specialty_score),
            },
            "comprehensive": {
                "raw_score": str(snapshot.performance_raw_score),
                "effective_score": str(snapshot.performance_score),
            },
        },
        "comprehensive_score": str(snapshot.comprehensive_score),
        "formula": "academic_score * academic_weight / 100 + academic + comprehensive",
        "rule_version_ids": snapshot.rule_version_ids,
        "cycle_policy_version_ids": snapshot.cycle_policy_version_ids,
        "input_digest": snapshot.input_digest,
        "updated_at": snapshot.updated_at.isoformat() + "Z",
        "entries": explained_entries,
    }

