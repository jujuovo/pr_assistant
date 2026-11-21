"""Transactional version switching for the future faculty scoring engine."""
import hashlib
import json

from sqlalchemy.exc import IntegrityError

from extensions import db
from material_models import MaterialRecord
from models import Student
from use_cases.faculty_policies import current_policy, lock_faculty_scoring, policies
from use_cases.structured_rules import StructuredRuleError
from workflow_models import FacultyScoringPolicy, ScoreEntry


def _draft(user, policy_id):
    row = policies(user).filter_by(id=policy_id).first()
    if row is None:
        raise StructuredRuleError("规则不存在", status_code=404)
    if row.status != "draft":
        raise StructuredRuleError("请选择草稿版本", status_code=409)
    return row


def _preview(row):
    scope = {"faculty_id": row.faculty_id, "cycle_code": row.cycle_code}
    current = FacultyScoringPolicy.query.filter_by(**scope, status="published").one_or_none()
    materials = MaterialRecord.query.with_entities(
        MaterialRecord.id, MaterialRecord.version, MaterialRecord.status
    ).filter_by(faculty_id=row.faculty_id, year=row.cycle_code).order_by(MaterialRecord.id).all()
    scores = ScoreEntry.query.with_entities(ScoreEntry.id, ScoreEntry.updated_at).filter_by(
        faculty_id=row.faculty_id, year=row.cycle_code, source_type="material"
    ).order_by(ScoreEntry.id).all()
    students = Student.query.with_entities(Student.student_id, Student.academic_score).filter_by(
        faculty_id=row.faculty_id
    ).order_by(Student.student_id).all()
    state = [scope, row.id, row.revision, row.sections, current.id if current else None,
             [tuple(item) for item in materials], [tuple(item) for item in scores],
             [tuple(item) for item in students]]
    digest = hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()
    previous = current.sections if current else {}
    return {**scope, "policy_id": row.id, "revision": row.revision, "digest": digest,
            "replaces_id": current.id if current else None,
            "changed_sections": sorted(key for key in previous.keys() | row.sections.keys()
                                       if previous.get(key) != row.sections.get(key)),
            "material_count": len(materials), "material_score_count": len(scores),
            "score_impact_available": False}


def preview_publication(user, policy_id):
    return _preview(_draft(user, policy_id))


def publish_policy(user, policy_id, expected_digest, *, apply_scoring):
    """Switch versions and apply scores in one transaction.

    The scoring adapter must validate all chapters and perform scoped recalculation
    without committing. No public route calls this until that adapter is connected.
    """
    row = _draft(user, policy_id)
    try:
        with db.session.begin_nested():
            lock_faculty_scoring(row.faculty_id)
            scope = policies(user).filter_by(cycle_code=row.cycle_code)
            changed = scope.filter_by(id=row.id, status="draft", revision=row.revision).update(
                {FacultyScoringPolicy.revision: FacultyScoringPolicy.revision},
                synchronize_session=False,
            )
            if not changed:
                raise StructuredRuleError("草稿已变化，请重新预览", status_code=409)
            preview = _preview(row)
            if preview["digest"] != expected_digest:
                raise StructuredRuleError("草稿或计分数据已变化，请重新预览", status_code=409)
            current = scope.filter_by(status="published").one_or_none()
            if current:
                current.status = "retired"
                db.session.flush()
            row.status = "published"
            db.session.flush()
            apply_scoring(row)
            db.session.flush()
    except IntegrityError as error:
        raise StructuredRuleError("发布状态冲突，请刷新后重试", status_code=409) from error
    db.session.commit()
    return row


def rebuild_policy_snapshots(policy):
    """Rebuild the scoped aggregate for students with material facts or an existing snapshot."""
    from use_cases.scoring import mark_draft_rankings_stale, rebuild_student_snapshot
    from workflow_models import StudentScoreSnapshot

    scope = {"faculty_id": policy.faculty_id, "year": policy.cycle_code}
    material_students = db.session.query(ScoreEntry.student_id).filter_by(
        **scope, source_type="material", status="active"
    )
    snapshot_students = db.session.query(StudentScoreSnapshot.student_id).filter_by(
        **scope, status="current"
    )
    students = Student.query.filter_by(faculty_id=policy.faculty_id).filter(
        Student.student_id.in_(material_students.union(snapshot_students).statement)
    ).order_by(Student.student_id).all()
    changes = []
    for student in students:
        before = StudentScoreSnapshot.query.filter_by(
            **scope, student_id=student.student_id, status="current"
        ).one_or_none()
        after, changed = rebuild_student_snapshot(student.student_id, policy.cycle_code)
        if changed:
            mark_draft_rankings_stale(student, policy.cycle_code, "学院推免总规则已修订")
            changes.append({
                "student_id": student.student_id,
                "before": str(before.comprehensive_score) if before else None,
                "after": str(after.comprehensive_score),
            })
    return changes


def _validate_supported_sections(row):
    import math

    fields = (
        ("学业成绩计算", "academic_score_weight", 100),
        ("学术专长封顶", "specialty_max_score", 100),
        ("综合表现封顶", "performance_max_score", 100),
        ("学科竞赛", "competition_max_count", None),
    )
    for section, key, maximum in fields:
        config = row.sections.get(section)
        value = config.get(key) if isinstance(config, dict) else None
        valid = (type(value) is int and value >= 0) if maximum is None else (
            type(value) in (int, float) and 0 <= value <= maximum and math.isfinite(value)
        )
        if not valid:
            raise StructuredRuleError(f"请填写有效的「{section}」参数 {key}")


def preview_supported_publication(user, policy_id):
    row = _draft(user, policy_id)
    _validate_supported_sections(row)
    result = _preview(row)
    with db.session.begin_nested() as simulation:
        current = current_policy(row.faculty_id, row.cycle_code)
        if current:
            current.status = "retired"
            db.session.flush()
        row.status = "published"
        db.session.flush()
        changes = rebuild_policy_snapshots(row)
        simulation.rollback()
    return {**result, "score_impact_available": True, "score_changes": changes}


def publish_supported_policy(user, policy_id, payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("digest"), str):
        raise StructuredRuleError("请先生成发布预览")
    _validate_supported_sections(_draft(user, policy_id))
    return publish_policy(user, policy_id, payload["digest"], apply_scoring=rebuild_policy_snapshots)
