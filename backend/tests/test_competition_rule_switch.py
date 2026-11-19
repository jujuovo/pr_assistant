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
