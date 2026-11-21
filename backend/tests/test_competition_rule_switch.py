import copy

import pytest

from extensions import db
from material_models import MaterialEvent, MaterialRecord
from use_cases.competition_review import review_competition_material
from use_cases.competition_rules import switch_competition_package
from workflow_models import CompetitionRulePackage, ScoreEntry, StudentScoreSnapshot

from test_competition_rule_correction_preview import _baseline


def _changed(snapshot):
    result = copy.deepcopy(snapshot)
    result["package_id"] = "xmu-competition-2028-corrected"
    result["score_matrix"]["national"]["first_or_above"]["A-"] = 12
    return result


def test_switch_preserves_old_package_and_invalidates_affected_score(env):
    admin, snapshot, old, row, teacher = _baseline(env)
    review_competition_material(teacher, row, {"version": row.version, "decision": "approve",
        "comment": "一致", "idempotency_key": "switch-approved"})
    result = switch_competition_package(admin, _changed(snapshot))
    db.session.flush()
    assert old.status == "retired" and old.current_scope_key is None
    new = db.session.get(CompetitionRulePackage, result["new_package_id"])
    assert new.status == "current" and new.version == old.version + 1
    assert row.status == "rule_reconfirmation_required"
    entry = ScoreEntry.query.one()
    assert entry.status == "invalidated" and entry.exclusion_reason == "rule_package_corrected"
    assert MaterialEvent.query.filter_by(action="competition_rule_invalidated").one()
    assert StudentScoreSnapshot.query.filter_by(student_id=row.student_id, status="current").one()


@pytest.mark.parametrize("fail_at", ["after_retire", "after_publish", "after_invalidation", "after_snapshot"])
def test_switch_failure_rolls_back_package_material_score_and_snapshot(env, fail_at):
    admin, snapshot, old, row, teacher = _baseline(env)
    review_competition_material(teacher, row, {"version": row.version, "decision": "approve",
        "comment": "一致", "idempotency_key": "rollback-approved"})
    db.session.commit()
    old_id, row_id = old.id, row.id
    with pytest.raises(RuntimeError):
        switch_competition_package(admin, _changed(snapshot), fail_at=fail_at)
    db.session.rollback()
    assert db.session.get(CompetitionRulePackage, old_id).status == "current"
    assert CompetitionRulePackage.query.count() == 1
    assert db.session.get(MaterialRecord, row_id).status == "scored"
    assert ScoreEntry.query.one().status == "active"
    assert MaterialEvent.query.filter_by(action="competition_rule_invalidated").count() == 0


def test_count_only_switch_reallocates_already_scored_material(env):
    admin, snapshot, old, row, teacher = _baseline(env)
    review_competition_material(teacher, row, {"version": row.version, "decision": "approve",
        "comment": "一致", "idempotency_key": "count-only"})
    changed = copy.deepcopy(snapshot)
    changed["policy"]["competition_max_count"] = 0
    result = switch_competition_package(admin, changed)
    entry = ScoreEntry.query.one()
    assert row.status == "scored" and entry.competition_rule_package_id == old.id
    assert entry.candidate_score > 0 and entry.effective_score == 0 and not entry.included
    assert result["snapshot_ids"]
    assert StudentScoreSnapshot.query.filter_by(status="superseded").count() == 1


def test_faculty_policy_reallocates_competition_and_preserves_candidate(env):
    from use_cases.competition_review import teacher_competition_summary
    from use_cases.faculty_policies import save_draft
    from use_cases.faculty_policy_publication import (
        preview_publication, publish_policy, rebuild_policy_snapshots,
    )

    admin, _snapshot, package, row, teacher = _baseline(env)
    review_competition_material(teacher, row, {"version": row.version, "decision": "approve",
        "comment": "一致", "idempotency_key": "faculty-limit"})
    before = ScoreEntry.query.one().candidate_score
    draft = save_draft(admin, {
        "title": "学院限项测试", "cycle_code": row.year,
        "sections": {
            "学业成绩计算": {"academic_score_weight": 80},
            "学术专长封顶": {"specialty_max_score": 15},
            "综合表现封顶": {"performance_max_score": 5},
            "学科竞赛": {"competition_max_count": 0},
        },
    })
    preview = preview_publication(admin, draft["id"])
    publish_policy(admin, draft["id"], preview["digest"], apply_scoring=rebuild_policy_snapshots)

    entry = ScoreEntry.query.one()
    assert entry.candidate_score == before
    assert entry.competition_rule_package_id == package.id
    assert entry.effective_score == 0
    assert not entry.included
    summary = teacher_competition_summary(teacher, row.student_id, row.year)
    assert summary["aggregate"]["total_effective_score"] == "0.0000"
    assert StudentScoreSnapshot.query.filter_by(status="superseded").count() == 1
