import pytest
from datetime import date

from extensions import db
from models import User
from use_cases.competition_review import review_competition_material, teacher_competition_summary
from use_cases.materials import MaterialUseCaseError, competition_workbench_summary
from use_cases.cycles import activate_cycle_policy, create_cycle_policy

from test_competition_review_command import _command, _submitted_competition


def test_teacher_summary_is_scoped_and_read_only(env):
    row, teacher = _submitted_competition(env)
    review_competition_material(teacher, row, _command(row))
    result = teacher_competition_summary(teacher, row.student_id, row.year)
    item = result["items"][0]
    assert item["project_name"] == "只读事实"
    assert item["candidate_score"] is not None
    assert item["effective_score"] is not None
    assert item["status"] == "scored"
    assert item["allowed_actions"] == ["open"]
    assert result["capabilities"] == {
        "editable": False, "mergeable": False, "score_override": False,
    }


def test_pending_summary_allows_return_but_never_edit_merge_or_override(env):
    row, teacher = _submitted_competition(env)
    item = teacher_competition_summary(teacher, row.student_id, row.year)["items"][0]
    assert item["allowed_actions"] == ["open", "return"]
    assert not ({"edit", "merge", "override_score"} & set(item["allowed_actions"]))


def test_teacher_cannot_read_cross_faculty_summary(env):
    row, _teacher = _submitted_competition(env)
    outsider = db.session.get(User, env[2]["other"])
    with pytest.raises(MaterialUseCaseError) as error:
        teacher_competition_summary(outsider, row.student_id, row.year)
    assert error.value.code == "forbidden"


def test_teacher_workbench_keeps_scored_material_in_read_only_history(env):
    row, teacher = _submitted_competition(env)
    review_competition_material(teacher, row, _command(row))
    admin = db.session.get(User, env[2]["admin"])
    cycle, _ = create_cycle_policy(
        admin, 2028, date(2025, 9, 1), date(2028, 8, 31), "2028 推免周期"
    )
    activate_cycle_policy(admin, cycle)
    result = competition_workbench_summary(teacher)
    assert result["pending_count"] == 0
    assert result["items"] == []
    history = result["reviewed_items"]
    assert [(item["id"], item["status"]) for item in history] == [(row.id, "scored")]
    assert set(history[0]["allowed_actions"]) == {"view", "download_attachment"}
    assert not ({"approve", "return", "edit", "override_score"} & set(history[0]["allowed_actions"]))


def test_teacher_history_excludes_drafts_and_abandoned_records(env):
    row, teacher = _submitted_competition(env)
    row.status = "abandoned"
    admin = db.session.get(User, env[2]["admin"])
    cycle, _ = create_cycle_policy(
        admin, 2028, date(2025, 9, 1), date(2028, 8, 31), "2028 推免周期"
    )
    activate_cycle_policy(admin, cycle)

    result = competition_workbench_summary(teacher)

    assert result["items"] == []
    assert result["reviewed_items"] == []
