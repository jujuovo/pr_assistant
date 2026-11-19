"""Read-only migration reconciliation services."""

import hashlib
import json
from collections import defaultdict
from decimal import Decimal

from domain.ranking import RankingCandidate, competition_ranking
from models import Application, Student
from automation_models import utcnow
from extensions import db
from workflow_models import (LegacyBackfillBatch, LegacyBackfillItem, RuleVersion,
                             ScoreEntry, StudentScoreSnapshot,
                             StructuredMaterialMigrationBatch,
                             StructuredMaterialMigrationItem)
from material_models import MaterialRecord
from use_cases.scoring import adapt_legacy_application
from domain.structured_rules import RuleCandidate, evaluate_candidate


def _decimal_text(value):
    return format(Decimal(str(value or 0)).quantize(Decimal("0.0000")), "f")


def legacy_reconciliation_report(year, *, faculty_id=None):
    """Compare legacy facts, unified entries/snapshots and ranking projections.

    This function intentionally performs queries only. Its stable digest excludes
    wall-clock metadata so the same database state produces the same report.
    """
    application_query = Application.query.filter_by(status="approved")
    student_query = Student.query.order_by(Student.student_id)
    if faculty_id is not None:
        application_query = application_query.filter_by(faculty_id=faculty_id)
        student_query = student_query.filter_by(faculty_id=faculty_id)

    detail_rows = []
    legacy_totals = defaultdict(lambda: Decimal("0"))
    issue_counts = defaultdict(int)
    for application in application_query.order_by(Application.id).all():
        if application.cycle_code not in (None, year):
            continue
        entry = ScoreEntry.query.filter_by(
            source_type="legacy_application", source_id=str(application.id)
        ).order_by(ScoreEntry.id).first()
        if entry is None:
            material = MaterialRecord.query.filter_by(application_id=application.id).first()
            if material:
                entry = ScoreEntry.query.filter_by(material_record_id=material.id).order_by(
                    ScoreEntry.id
                ).first()
        published_version = None
        if application.rule_id is not None:
            versions = RuleVersion.query.filter_by(
                rule_id=application.rule_id, status="published"
            ).order_by(RuleVersion.version.desc(), RuleVersion.id.desc()).all()
            published_version = next(
                (version for version in versions
                 if version.snapshot.get("cycle_code") in (None, application.cycle_code)),
                None,
            )
        expected = (
            Decimal(str(application.final_score))
            if application.final_score is not None
            else None
        )
        if expected is not None and application.cycle_code == year:
            legacy_totals[application.student_id] += expected
        issues = []
        if application.cycle_code is None:
            issues.append("missing_fixed_cycle")
        if published_version is None:
            issues.append("missing_applicable_rule")
        if entry is None:
            issues.append("approved_without_score_entry")
        elif application.cycle_code is not None and entry.year != application.cycle_code:
            issues.append("score_cycle_mismatch")
        if entry is not None and published_version is not None and entry.rule_version_id != published_version.id:
            issues.append("rule_version_mismatch")
        if entry is not None and expected is not None and entry.effective_score != expected:
            issues.append("score_mismatch")
        for issue in issues:
            issue_counts[issue] += 1
        state = issues[0] if issues else "matched"
        detail_rows.append(
            {
                "application_id": application.id,
                "student_id": application.student_id,
                "state": state,
                "issues": issues,
                "fixed_cycle_code": application.cycle_code,
                "candidate_cycle_code": None if application.cycle_code is None else application.cycle_code,
                "legacy_score": _decimal_text(expected),
                "score_entry_id": entry.id if entry else None,
                "unified_score": _decimal_text(entry.effective_score) if entry else None,
                "rule_version_id": entry.rule_version_id if entry else None,
            }
        )

    students = student_query.all()
    summary_rows = []
    ranking_candidates = []
    for student in students:
        entries = ScoreEntry.query.filter_by(
            student_id=student.student_id, year=year, status="active"
        ).all()
        unified_total = sum(
            (Decimal(str(entry.effective_score)) for entry in entries), Decimal("0")
        )
        legacy_total = legacy_totals[student.student_id]
        snapshot = StudentScoreSnapshot.query.filter_by(
            student_id=student.student_id, year=year, status="current"
        ).order_by(StudentScoreSnapshot.version.desc()).first()
        summary_rows.append(
            {
                "student_id": student.student_id,
                "legacy_bonus_total": _decimal_text(legacy_total),
                "unified_bonus_total": _decimal_text(unified_total),
                "bonus_delta": _decimal_text(unified_total - legacy_total),
                "legacy_comprehensive_score": (
                    _decimal_text(student.comprehensive_score)
                    if student.comprehensive_score is not None else None
                ),
                "snapshot_comprehensive_score": (
                    _decimal_text(snapshot.comprehensive_score) if snapshot else None
                ),
                "issues": (["missing_snapshot"] if snapshot is None else [])
                          + (["legacy_summary_difference"] if unified_total != legacy_total else []),
            }
        )
        if snapshot is None:
            issue_counts["missing_snapshot"] += 1
        if unified_total != legacy_total:
            issue_counts["legacy_summary_difference"] += 1
        ranking_candidates.append(
            RankingCandidate(
                student.student_id,
                Decimal(str(snapshot.comprehensive_score)) if snapshot else None,
                snapshot.id if snapshot else None,
                snapshot is not None and student.academic_score is not None,
                None if snapshot is not None else "missing_score_snapshot",
            )
        )

    projected = {
        item.student_id: item for item in competition_ranking(ranking_candidates)
    }
    ranking_rows = [
        {
            "student_id": student.student_id,
            "legacy_rank": student.major_ranking,
            "projected_rank": projected[student.student_id].rank,
            "different": student.major_ranking != projected[student.student_id].rank,
        }
        for student in students
    ]
    material_rows = []
    material_issue_keys = (
        "evidence_date_conflict", "missing_confirmation_snapshot",
        "uncovered_structured_terms", "ambiguous_structured_rules",
        "incorrect_default_rule",
    )
    material_query = MaterialRecord.query.order_by(MaterialRecord.id)
    if faculty_id is not None:
        material_query = material_query.filter_by(faculty_id=faculty_id)
    for material in material_query.all():
        if material.cycle_policy_version_id is not None and material.year != year:
            continue
        issues = []
        confirmed = material.confirmed_terms if isinstance(material.confirmed_terms, dict) else None
        normalized = material.normalized_terms if isinstance(material.normalized_terms, dict) else None
        ocr = material.ocr_raw_terms if isinstance(material.ocr_raw_terms, dict) else None
        saved_date = (material.data or {}).get("award_date")
        confirmed_date = (normalized or {}).get("award_date")
        ocr_date = (ocr or {}).get("award_date") or (ocr or {}).get("date")
        if not confirmed or not normalized:
            issues.append("missing_confirmation_snapshot")
        if confirmed_date and saved_date and confirmed_date != saved_date:
            issues.append("evidence_date_conflict")
        elif ocr_date and confirmed_date and ocr_date != confirmed_date:
            issues.append("evidence_date_conflict")
        if material.status == "rule_unmatched":
            issues.append("uncovered_structured_terms")
        if normalized:
            try:
                from use_cases.materials import match_material_rule
                match = match_material_rule(material, year)
                if match["status"] == "ambiguous":
                    issues.append("ambiguous_structured_rules")
            except ValueError:
                pass
        if material.rule_version_id and normalized:
            bound = db.session.get(RuleVersion, material.rule_version_id)
            snapshot = bound.snapshot if bound else {}
            terms = snapshot.get("match_terms")
            if isinstance(terms, dict):
                candidate = RuleCandidate(
                    version_id=bound.id, cycle_code=snapshot.get("cycle_code"),
                    faculty_id=snapshot.get("faculty_id"),
                    material_category=snapshot.get("sub_type"), terms=terms,
                    score=snapshot.get("score"),
                )
                matched, _explanation = evaluate_candidate(
                    candidate, cycle_code=year, faculty_id=material.faculty_id,
                    material_category=material.category, terms=normalized,
                )
                if not matched:
                    issues.append("incorrect_default_rule")
        issues = list(dict.fromkeys(issues))
        for issue in issues:
            issue_counts[issue] += 1
        if issues:
            student = next((item for item in students
                            if item.student_id == material.student_id), None)
            material_rows.append({
                "material_record_id": material.id,
                "student_id": material.student_id,
                "issues": issues,
                "ocr_award_date": ocr_date,
                "confirmed_award_date": confirmed_date,
                "saved_award_date": saved_date,
                "bound_rule_version_id": material.rule_version_id,
                "affected_ranking_scope": {
                    "year": year, "faculty_id": material.faculty_id,
                    "major_id": student.major_id if student else None,
                },
            })
    manual_review = []
    release_blocks = []
    for detail in detail_rows:
        unresolved = [issue for issue in detail["issues"] if issue in {
            "missing_fixed_cycle", "missing_applicable_rule",
            "approved_without_score_entry", "score_cycle_mismatch",
        }]
        if not unresolved:
            continue
        manual_review.append({
            "application_id": detail["application_id"],
            "student_id": detail["student_id"],
            "issues": unresolved,
            "required_evidence": {
                "cycle_policy_version_id": None,
                "rule_version_id": detail["rule_version_id"],
                "evidence_type": None,
                "evidence_reference": None,
                "confirmed_by": None,
            },
            "prohibited_inference": "award_date_year",
        })
        release_blocks.append({
            "code": "historical_scoring_unresolved",
            "year": year,
            "faculty_id": faculty_id,
            "application_id": detail["application_id"],
            "reasons": unresolved,
        })
    for material in material_rows:
        release_blocks.append({
            "code": "structured_material_unresolved",
            **material["affected_ranking_scope"],
            "material_record_id": material["material_record_id"],
            "reasons": material["issues"],
        })
    report = {
        "year": year,
        "faculty_id": faculty_id,
        "details": detail_rows,
        "students": summary_rows,
        "ranking_scope": ranking_rows,
        "material_issues": material_rows,
        "manual_review": manual_review,
        "release_blocks": release_blocks,
        "issue_counts": {key: issue_counts.get(key, 0) for key in (
            "missing_fixed_cycle", "missing_applicable_rule",
            "approved_without_score_entry", "score_cycle_mismatch",
            "missing_snapshot", "legacy_summary_difference",
        ) + material_issue_keys},
        "blocking_difference_count": (
            sum(row["state"] != "matched" for row in detail_rows)
            + sum(row["bonus_delta"] != "0.0000" for row in summary_rows)
            + sum(row["different"] for row in ranking_rows)
            + len(material_rows)
        ),
        "ranking_release_allowed": not release_blocks,
    }
    canonical = json.dumps(report, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    report["digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return report


def run_legacy_backfill(year, *, batch_key, backup_reference,
                        cycle_policy_version_id=None, mappings=None, max_items=None):
    if not backup_reference or not backup_reference.strip():
        raise ValueError("verified backup reference is required")
    from workflow_models import RecommendationCyclePolicy
    policy = db.session.get(RecommendationCyclePolicy, cycle_policy_version_id)
    if policy is None or policy.cycle_code != year:
        raise ValueError("explicit cycle policy version for the repair year is required")
    mapping_by_id = {int(item["application_id"]): item for item in (mappings or [])}
    for item in mapping_by_id.values():
        if not item.get("evidence_reference") or not item.get("confirmed_by") or not item.get("rule_version_id"):
            raise ValueError("each mapping requires rule version, evidence reference and confirmer")
    batch = LegacyBackfillBatch.query.filter_by(batch_key=batch_key).first()
    if batch is None:
        batch = LegacyBackfillBatch(batch_key=batch_key, year=year,
            backup_reference=backup_reference.strip(), cycle_policy_version_id=policy.id,
            evidence_manifest=list(mapping_by_id.values()), status="running")
        db.session.add(batch)
        db.session.commit()
    elif (batch.year != year or batch.cycle_policy_version_id != policy.id
          or batch.backup_reference != backup_reference.strip()
          or (batch.evidence_manifest or []) != list(mapping_by_id.values())):
        raise ValueError("batch key already belongs to different repair evidence")
    done_ids = {row.application_id for row in LegacyBackfillItem.query.filter_by(batch_id=batch.id)}
    query = Application.query.filter_by(status="approved").order_by(Application.id)
    candidates = [application for application in query.all()
                  if application.cycle_code == year or application.id in mapping_by_id]
    missing_evidence = [application.id for application in candidates
                        if application.id not in mapping_by_id]
    if missing_evidence:
        raise ValueError(f"explicit mapping evidence required for applications: {missing_evidence}")
    processed = 0
    for application in candidates:
        if application.id in done_ids:
            continue
        if max_items is not None and processed >= max_items:
            break
        try:
            mapping = mapping_by_id.get(application.id)
            if application.cycle_code is None:
                application.cycle_code = year
                application.cycle_policy_version_id = policy.id
            if application.cycle_code != year or application.cycle_policy_version_id != policy.id:
                raise ValueError("application fixed cycle does not match repair policy")
            rule_version_id = mapping.get("rule_version_id") if mapping else None
            result = adapt_legacy_application(
                application, year=year, rule_version_id=rule_version_id
            )
            item = LegacyBackfillItem(batch_id=batch.id, application_id=application.id,
                                      status=result["status"], result=result)
            db.session.add(item)
            batch.processed_count += 1
        except Exception as error:
            db.session.rollback()
            batch = db.session.get(LegacyBackfillBatch, batch.id)
            db.session.add(LegacyBackfillItem(batch_id=batch.id, application_id=application.id,
                status="failed", error=f"{type(error).__name__}: {error}"))
            batch.processed_count += 1
            batch.failed_count += 1
        batch.updated_at = utcnow()
        db.session.commit()
        processed += 1
    remaining = any(a.id not in {row.application_id for row in LegacyBackfillItem.query.filter_by(batch_id=batch.id)}
                    for a in candidates)
    batch.status = "running" if remaining else ("completed_with_errors" if batch.failed_count else "completed")
    batch.updated_at = utcnow()
    db.session.commit()
    return batch


def run_structured_material_migration(*, batch_key, backup_reference, max_items=None,
                                      normalizer=None):
    """Normalize only explicit student confirmations; never promote OCR or score."""
    if not isinstance(backup_reference, str) or not backup_reference.strip():
        raise ValueError("verified backup reference is required")
    if not isinstance(batch_key, str) or not batch_key.strip():
        raise ValueError("batch key is required")
    batch = StructuredMaterialMigrationBatch.query.filter_by(batch_key=batch_key).first()
    if batch is None:
        batch = StructuredMaterialMigrationBatch(
            batch_key=batch_key.strip(), backup_reference=backup_reference.strip(),
            status="running",
        )
        db.session.add(batch); db.session.commit()
    elif batch.backup_reference != backup_reference.strip():
        raise ValueError("batch key already belongs to a different backup")
    from domain.material_terms import NORMALIZATION_VERSION, normalize_confirmed_terms
    normalize = normalizer or normalize_confirmed_terms
    done_ids = {item.material_record_id for item in
                StructuredMaterialMigrationItem.query.filter_by(batch_id=batch.id).all()}
    candidates = MaterialRecord.query.order_by(MaterialRecord.id).all()
    processed = 0
    for row in candidates:
        if row.id in done_ids or (max_items is not None and processed >= max_items):
            continue
        try:
            confirmed = row.confirmed_terms
            if not isinstance(confirmed, dict):
                action = "correction_required"
                result = {"reason": "missing_student_confirmation",
                          "ocr_promoted": False, "score_written": False}
            else:
                normalized = normalize(confirmed)
                confirmed_date = normalized.get("award_date")
                saved_date = (row.data or {}).get("award_date")
                if confirmed_date and saved_date and confirmed_date != saved_date:
                    action = "correction_required"
                    result = {"reason": "confirmed_saved_date_conflict",
                              "confirmed_award_date": confirmed_date,
                              "saved_award_date": saved_date,
                              "score_written": False}
                elif row.normalized_terms is None:
                    row.normalized_terms = normalized
                    row.normalization_version = NORMALIZATION_VERSION
                    action = "normalized_from_student_confirmation"
                    result = {"normalization_version": NORMALIZATION_VERSION,
                              "score_written": False}
                else:
                    action = "unchanged"
                    result = {"reason": "already_normalized", "score_written": False}
            db.session.add(StructuredMaterialMigrationItem(
                batch_id=batch.id, material_record_id=row.id,
                status=action, result=result,
            ))
            batch.processed_count += 1
            db.session.commit()
        except Exception as error:
            db.session.rollback()
            batch = db.session.get(StructuredMaterialMigrationBatch, batch.id)
            db.session.add(StructuredMaterialMigrationItem(
                batch_id=batch.id, material_record_id=row.id, status="failed",
                error=f"{type(error).__name__}: {error}",
            ))
            batch.processed_count += 1; batch.failed_count += 1
            db.session.commit()
        processed += 1
    handled = {item.material_record_id for item in
               StructuredMaterialMigrationItem.query.filter_by(batch_id=batch.id).all()}
    batch.status = ("running" if any(row.id not in handled for row in candidates)
                    else ("completed_with_errors" if batch.failed_count else "completed"))
    batch.updated_at = utcnow(); db.session.commit()
    items = StructuredMaterialMigrationItem.query.filter_by(batch_id=batch.id).order_by(
        StructuredMaterialMigrationItem.material_record_id).all()
    return {
        "batch_id": batch.id, "status": batch.status,
        "processed_count": batch.processed_count, "failed_count": batch.failed_count,
        "correction_list": [item.material_record_id for item in items
                            if item.status == "correction_required"],
        "items": [{"material_record_id": item.material_record_id,
                   "status": item.status, "result": item.result,
                   "error": item.error} for item in items],
    }
