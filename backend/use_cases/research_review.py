"""Research evidence review, using the shared score ledger and snapshot transaction."""
import hashlib
import json

from automation_models import utcnow
from domain.research_scoring import POLICY_VERSION, candidate
from extensions import db
from material_models import MaterialRecord
from models import Student
from services.materials.schemas import RESEARCH_TYPES, integer, normalize_research, object_keys, text
from use_cases.materials import MaterialUseCaseError, _authorize_transition, _cas_change, _event
from use_cases.scoring import rebuild_student_snapshot, mark_draft_rankings_stale
from workflow_models import MaterialReviewCommand, RuleVersion, ScoreEntry, RecommendationCyclePolicy


def allocate_research(entries):
    seen = set()
    c_count = 0
    for entry in sorted(entries, key=lambda item: (-item.candidate_score, item.id)):
        basis = entry.exclusion_basis
        identity = (entry.category, basis["work_key"])
        reason = None
        if not entry.candidate_score:
            reason = basis["basis"]
        elif identity in seen:
            reason = "同一成果只计一次"
        elif basis["basis"] == "CCF-C" and c_count == 2:
            reason = "C类论文限两篇，按个人得分取高"
        else:
            seen.add(identity)
            c_count += basis["basis"] == "CCF-C"
        entry.included = reason is None
        entry.effective_score = entry.candidate_score if entry.included else 0
        entry.exclusion_reason = reason


def review_research(user, row, payload):
    return review_policy_material(user, row, payload, POLICY_VERSION, normalize_research, candidate, "work_key")


def review_policy_material(user, row, payload, policy_version, normalize_facts, score_candidate, identity_field):
    object_keys(payload, {"version", "decision", "comment", "idempotency_key", "verified_facts"},
                {"version", "decision", "comment", "idempotency_key"})
    version = integer(payload["version"], "version", 1, 2_000_000_000)
    key = text(payload["idempotency_key"], "幂等键", maximum=128)
    comment = text(payload["comment"], "核验意见", maximum=2000)
    decision = payload["decision"]
    if user.role not in {"teacher", "admin"} or user.faculty_id != row.faculty_id:
        raise MaterialUseCaseError("没有本学院审核权限", status_code=403)
    if decision not in ("verified", "rejected", "needs_correction"):
        raise ValueError("核验结论无效")
    digest = hashlib.sha256(json.dumps([row.id, user.id, payload], sort_keys=True).encode()).hexdigest()
    student = Student.query.filter_by(student_id=row.student_id).with_for_update().one()
    previous = MaterialReviewCommand.query.filter_by(record_id=row.id, idempotency_key=key).first()
    if previous:
        if previous.request_digest != digest:
            raise MaterialUseCaseError("幂等键冲突", code="idempotency_conflict", status_code=409)
        return previous.result, True
    rule = db.session.get(RuleVersion, row.rule_version_id)
    policy = db.session.get(RecommendationCyclePolicy, row.cycle_policy_version_id)
    if not rule or not policy or row.normalization_version != policy_version:
        raise MaterialUseCaseError("材料未固定适用版本", status_code=409)
    from domain.student_work_scoring import POLICY_VERSION as WORK_POLICY
    is_work = policy_version == WORK_POLICY
    facts = None
    target = decision
    if decision == "verified":
        facts = normalize_facts(row.category, payload.get("verified_facts"), verified=True)
        if is_work:
            assessments = facts["assessments"]
            if {a["appointment_index"] for a in assessments} != set(range(len(row.data["appointments"]))):
                raise ValueError("须逐条对应材料中的任职记录")
            legacy = [entry.source_id for entry in ScoreEntry.query.filter_by(student_id=row.student_id,
                      year=row.year, category="student_work", status="active").all()
                      if (entry.exclusion_basis or {}).get("policy") != WORK_POLICY]
            if legacy:
                raise MaterialUseCaseError("须先核对历史干部记录：" + ", ".join(map(str, legacy)), status_code=409)
        cutoff = f"{policy.eligible_award_end_date.year}-08-31"
        score, basis = score_candidate(row.category, facts, cutoff)
        target = "scored" if score else "verified_not_eligible"
    _authorize_transition(user, row, "review", target)
    _cas_change(row, version, ("submitted", "under_review"), {"status": target, "confirmed_terms": facts})
    scoring = {}
    if decision != "needs_correction":
        ancestor = row
        while ancestor.supersedes_record_id:
            ancestor = db.session.get(MaterialRecord, ancestor.supersedes_record_id)
            for old in ScoreEntry.query.filter_by(material_record_id=ancestor.id, status="active"):
                old.status = "invalidated"
                old.included = False
                old.invalidated_at = utcnow()
                old.invalidated_reason = comment
        if facts is not None:
            recognition = {"policy": policy_version, "basis": basis, "cutoff": cutoff}
            if identity_field:
                identity = facts[identity_field]
                recognition[identity_field] = identity.casefold() if identity_field == "work_key" else identity
            entry = ScoreEntry(student_id=row.student_id, faculty_id=row.faculty_id, year=row.year,
                cycle_policy_version_id=policy.id, score_group="comprehensive" if is_work else "academic", category=row.category,
                source_type="material", source_id=str(row.id), source_revision=version,
                material_record_id=row.id, rule_version_id=rule.id, candidate_score=score,
                raw_score=score, adjusted_score=score, effective_score=score,
                exclusion_basis=recognition, idempotency_key=row.category + ":" + digest)
            db.session.add(entry)
            db.session.flush()
            scoring["score_entry_id"] = entry.id
        snapshot, changed = rebuild_student_snapshot(row.student_id, row.year)
        scoring["snapshot_id"] = snapshot.id
        if changed:
            mark_draft_rankings_stale(student, row.year, "材料核验结果变化")
    result = {"record_id": row.id, "version": row.version, "status": row.status, "scoring": scoring}
    _event(row, user, "reviewed", {**result, "decision": decision, "comment": comment,
           "data_snapshot": row.data, "verified_facts": facts, "rule_version_id": rule.id,
           "policy": policy_version, "attachments_snapshot": [a.sha256 for a in row.attachments]})
    db.session.add(MaterialReviewCommand(record_id=row.id, idempotency_key=key, request_digest=digest,
                                         result=result, created_by=user.id))
    db.session.flush()
    return result, False
