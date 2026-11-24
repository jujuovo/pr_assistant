"""Atomic teacher review and scoring for package-bound competition evidence."""
import hashlib
import json
from decimal import Decimal

from automation_models import utcnow
from domain.competition_scoring import (
    CompetitionAggregationCandidate, aggregate_competition_candidates,
)
from use_cases.faculty_policies import lock_faculty_scoring
from extensions import db
from material_models import MaterialEvent, MaterialRecord
from models import Student
from use_cases.materials import MaterialUseCaseError, validate_competition_review_command
from use_cases.scoring import mark_draft_rankings_stale, rebuild_student_snapshot
from workflow_models import (
    CompetitionRulePackage, MaterialReviewCommand, ScoreEntry, StudentScoreSnapshot,
)


def _digest(row, user, command):
    value = {"record_id": row.id, "actor_id": user.id, **command}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()


def _aggregate(student_id, year, package):
    packages = CompetitionRulePackage.query.filter_by(cycle_code=year, scope_key=package.scope_key).all()
    current = next(item for item in packages if item.status == "current")
    entries = ScoreEntry.query.filter_by(
        student_id=student_id, year=year, category="competition", status="active"
    ).filter(ScoreEntry.competition_rule_package_id.in_([item.id for item in packages])).order_by(ScoreEntry.id).all()
    limit = current.snapshot["policy"]["competition_max_count"]
    return allocate_competition_entries(entries, limit, {"allocation_package_id": current.id})


def allocate_competition_entries(entries, limit, basis):
    package_ids = {entry.competition_rule_package_id for entry in entries}
    packages = CompetitionRulePackage.query.filter(CompetitionRulePackage.id.in_(package_ids)).all()
    catalogs = {item.id: {row["competition_id"]: (index, row) for index, row in
                          enumerate(item.snapshot["catalog"])} for item in packages}
    materials = {row.id: row for row in MaterialRecord.query.filter(
        MaterialRecord.id.in_([entry.material_record_id for entry in entries])
    ).all()} if entries else {}
    candidates = []
    for entry in entries:
        row = materials[entry.material_record_id]
        facts = row.confirmed_terms or {}
        order, catalog = catalogs[entry.competition_rule_package_id][facts["competition_id"]]
        candidates.append(CompetitionAggregationCandidate(
            material_id=row.id, competition_id=facts["competition_id"],
            event_family=catalog["event_family"], event_year=facts["event_year"],
            candidate_score=entry.candidate_score,
            work_key=row.competition_work_group_key or str(row.id),
            event_key=row.competition_event_group_key or str(row.id),
            evidence_date=facts["award_date"], rule_order=order,
        ))
    result = aggregate_competition_candidates(candidates, max_count=limit)
    by_material = {item.material_id: item for item in result.items}
    for entry in entries:
        allocation = by_material[entry.material_record_id]
        entry.effective_score = allocation.effective_score
        entry.included = allocation.included
        entry.exclusion_reason = allocation.exclusion_reason
        entry.exclusion_stage = allocation.exclusion_reason
        entry.exclusion_basis = {"policy": "competition-2028", "deterministic": True,
                                 **basis, "max_count": limit}
        entry.updated_at = utcnow()
    return result


def review_competition_material(user, row, payload, *, fail_at=None):
    command = validate_competition_review_command(user, row, payload)
    lock_faculty_scoring(row.faculty_id)
    request_digest = _digest(row, user, command)
    previous = MaterialReviewCommand.query.filter_by(
        record_id=row.id, idempotency_key=command["idempotency_key"]
    ).first()
    if previous:
        if previous.request_digest != request_digest:
            raise MaterialUseCaseError("同一幂等键不能用于不同审核请求",
                code="idempotency_conflict", status_code=409)
        return previous.result, True
    locked = MaterialRecord.query.filter_by(id=row.id).with_for_update().one()
    student = Student.query.filter_by(student_id=locked.student_id).with_for_update().one()
    if locked.version != command["version"]:
        raise MaterialUseCaseError("材料版本已变化", code="version_conflict", status_code=409)
    if locked.status not in {"submitted", "under_review"}:
        raise MaterialUseCaseError("材料不在可审核状态", code="review_not_available", status_code=409)
    package = db.session.get(CompetitionRulePackage, locked.competition_rule_package_id)
    if not package:
        raise MaterialUseCaseError("固定竞赛规则包不存在", code="rule_package_missing", status_code=409)
    from services.competition_ocr.assessment import assessment
    advice=assessment(locked)
    if command["decision"]=="approve" and locked.ocr_raw_terms and advice["review_mode"]=="manual_confirmation" and command.get("ocr_confirmed") is not True:
        raise MaterialUseCaseError("请人工核对OCR差异、缺失依据及申报分数后明确确认",code="ocr_manual_confirmation_required",status_code=409)
    if fail_at == "after_lock": raise RuntimeError("injected after_lock failure")
    from services.materials.originals import verify_ocr_originals
    verify_ocr_originals(locked)
    from services.competition_ocr.binding import record_links
    ocr_snapshot = record_links(locked)
    locked.version += 1
    locked.status = "needs_correction" if command["decision"] == "return" else "scored"
    if command["decision"] == "approve":
        candidate = Decimal(str((locked.analysis or {})["candidate_score"]))
        entry = ScoreEntry(
            student_id=locked.student_id, faculty_id=locked.faculty_id, year=locked.year,
            cycle_policy_version_id=locked.cycle_policy_version_id,
            score_group="academic", category="competition", source_type="material",
            source_id=str(locked.id), source_revision=command["version"], material_record_id=locked.id,
            competition_rule_package_id=package.id, candidate_score=candidate,
            competition_work_group_key=locked.competition_work_group_key,
            competition_event_group_key=locked.competition_event_group_key,
            raw_score=candidate, adjusted_score=candidate, effective_score=candidate,
            included=True, status="active",
            idempotency_key=f"competition:{locked.id}:{command['version']}:{command['idempotency_key']}",
        )
        db.session.add(entry); db.session.flush()
        if fail_at == "after_entry": raise RuntimeError("injected after_entry failure")
        from use_cases.faculty_policies import current_policy
        policy = current_policy(locked.faculty_id, locked.year)
        if not policy:
            _aggregate(locked.student_id, locked.year, package)
        snapshot, _ = rebuild_student_snapshot(locked.student_id, locked.year)
        stale = mark_draft_rankings_stale(student, locked.year, "competition score changed")
        scoring = {"score_entry_id": entry.id, "snapshot_id": snapshot.id,
                   "competition_total": student_competition_total(locked.student_id, locked.year),
                   "stale_ranking_batch_ids": [batch.id for batch in stale]}
    else:
        scoring = None
    if fail_at == "before_audit": raise RuntimeError("injected before_audit failure")
    details = {**command, "version": locked.version, "scoring": scoring,
               "data_snapshot": locked.data, "ocr_links_snapshot": ocr_snapshot,
               "ocr_assessment_snapshot": advice, "ocr_raw_snapshot":locked.ocr_raw_terms}
    db.session.add(MaterialEvent(record_id=locked.id, actor_id=user.id,
        action="competition_approved" if command["decision"] == "approve" else "competition_returned",
        details=details))
    result = {"record_id": locked.id, "status": locked.status, "version": locked.version,
              "decision": command["decision"], "scoring": scoring}
    db.session.add(MaterialReviewCommand(record_id=locked.id,
        idempotency_key=command["idempotency_key"], request_digest=request_digest,
        result=result, created_by=user.id))
    db.session.flush()
    return result, False


def teacher_competition_summary(user, student_id, year, *, reviewed_only=False):
    if user is None or user.role != "teacher" or not user.faculty_id:
        raise MaterialUseCaseError("只有授权教师可以查看竞赛汇总", code="forbidden", status_code=403)
    student = Student.query.filter_by(student_id=student_id).first()
    if student is None or student.faculty_id != user.faculty_id:
        raise MaterialUseCaseError("无权查看该学生竞赛汇总", code="forbidden", status_code=403)
    base = MaterialRecord.query.filter_by(
        student_id=student_id, faculty_id=user.faculty_id, year=year, category="competition"
    )
    # 明细只给教师看学生真正申报过的材料：草稿还没提交，放弃的更不该算进汇总，
    # 否则教师看到的"材料总数"里会混进学生自己删掉的东西。
    hidden_rows = base.filter(
        MaterialRecord.status.in_(("draft", "abandoned"))
    ).all()
    hidden = {}
    for row in hidden_rows:
        hidden[row.status] = hidden.get(row.status, 0) + 1
    visible = (
        MaterialRecord.status.in_(("verified", "rejected", "needs_correction", "scored", "verified_not_eligible"))
        if reviewed_only
        else ~MaterialRecord.status.in_(("draft", "abandoned"))
    )
    rows = base.filter(visible).order_by(MaterialRecord.id).all()
    superseded_by = {}
    if rows:
        for successor in MaterialRecord.query.filter(
            MaterialRecord.supersedes_record_id.in_([row.id for row in rows]),
            MaterialRecord.status != "abandoned",
        ).order_by(MaterialRecord.id).all():
            superseded_by[successor.supersedes_record_id] = successor.id
    entries = {entry.material_record_id: entry for entry in ScoreEntry.query.filter(
        ScoreEntry.material_record_id.in_([row.id for row in rows]), ScoreEntry.status == "active"
    ).all()} if rows else {}
    items = []
    for row in rows:
        facts = row.confirmed_terms or row.data
        entry = entries.get(row.id)
        actions = ["open"]
        if row.status in {"submitted", "under_review"}:
            actions.append("return")
        items.append({
            "record_id": row.id, "material_version": row.version,
            "project_name": facts.get("project_name"),
            "competition_id": facts.get("competition_id"),
            "level": facts.get("level"), "award": facts.get("award"),
            "award_date": facts.get("award_date"), "event_year": facts.get("event_year"),
            "participation_mode": facts.get("participation_mode"),
            "supersedes_record_id": row.supersedes_record_id,
            "superseded_by_record_id": superseded_by.get(row.id),
            "key_facts": facts, "status": row.status,
            "candidate_score": str(entry.candidate_score) if entry else (row.analysis or {}).get("candidate_score"),
            "effective_score": str(entry.effective_score) if entry else None,
            "included": entry.included if entry else None,
            "exclusion_reason": entry.exclusion_reason if entry else None,
            "attachments": [{"id": item.id, "filename": item.filename,
                "url": f"/api/materials/competition/records/{row.id}/attachments/{item.id}"}
                for item in row.attachments],
            "allowed_actions": actions,
        })
    return {"student_id": student_id, "year": year, "items": items,
            "aggregate": _summary_aggregate(rows, entries, year, hidden),
            "capabilities": {"editable": False, "mergeable": False, "score_override": False}}


def _summary_aggregate(rows, entries, year, hidden=None):
    """把逐条明细压成可供教师判断的合计；只做汇总，不重算也不改写任何分数。"""
    from collections import Counter

    hidden = hidden or {}
    status_counts = Counter(row.status for row in rows)
    active = [entry for entry in entries.values() if entry.included]
    excluded = [entry for entry in entries.values() if entry.included is False]
    zero = Decimal("0")

    def total(values):
        return str(sum((Decimal(value) for value in values), zero).quantize(Decimal("0.0001")))

    return {
        "cycle_code": year,
        "record_count": len(rows),
        "status_counts": dict(status_counts),
        # 未计入明细的两类单独计数，教师才能把总数算平
        "draft_count": hidden.get("draft", 0),
        "abandoned_count": hidden.get("abandoned", 0),
        "pending_count": sum(status_counts.get(status, 0) for status in
                             ("draft", "submitted", "under_review")),
        "included_count": len(active),
        "excluded_count": len(excluded),
        # 候选分统计所有已出分项，计入分只统计被采纳项；
        # 两者相等说明没有被规则排除的材料，不等才有排除发生。
        "total_candidate_score": total(entry.candidate_score for entry in entries.values()),
        "total_effective_score": total(entry.effective_score for entry in active),
    }


def student_competition_feedback(user, year):
    if user is None or user.role != "student" or not user.student_id:
        raise MaterialUseCaseError("只能读取本人竞赛反馈", code="forbidden", status_code=403)
    entries = ScoreEntry.query.filter_by(
        student_id=user.student_id, year=year, category="competition", status="active"
    ).order_by(ScoreEntry.id).all()
    packages = {item.id: item for item in CompetitionRulePackage.query.filter(
        CompetitionRulePackage.id.in_({entry.competition_rule_package_id for entry in entries})
    ).all()} if entries else {}
    materials = {item.id: item for item in MaterialRecord.query.filter(
        MaterialRecord.id.in_([entry.material_record_id for entry in entries])
    ).all()} if entries else {}
    items = []
    for entry in entries:
        material = materials[entry.material_record_id]; package = packages[entry.competition_rule_package_id]
        facts = material.confirmed_terms or material.data
        items.append({"material_id": material.id, "status": material.status,
            "competition_id": facts.get("competition_id"),
            "project_name": facts.get("project_name"),
            "candidate_score": str(entry.candidate_score),
            "effective_score": str(entry.effective_score), "included": entry.included,
            "exclusion_reason": entry.exclusion_reason,
            "rule_package": {"package_id": package.package_id, "version": package.version,
                             "digest": package.digest}})
    snapshot = StudentScoreSnapshot.query.filter_by(
        student_id=user.student_id, year=year, status="current"
    ).order_by(StudentScoreSnapshot.version.desc()).first()
    return {"student_id": user.student_id, "year": year, "items": items,
        "competition_total": str(sum((entry.effective_score for entry in entries if entry.included), Decimal("0"))),
        "cycle_snapshot": ({"status": "current", "snapshot_id": snapshot.id,
            "version": snapshot.version, "comprehensive_score": str(snapshot.comprehensive_score)}
            if snapshot else {"status": "no_authoritative_snapshot"})}



def student_competition_total(student_id, year):
    entries = ScoreEntry.query.filter_by(student_id=student_id, year=year,
        category="competition", status="active", source_type="material", included=True).all()
    return str(sum((entry.effective_score for entry in entries), Decimal("0")).quantize(Decimal("0.0001")))
