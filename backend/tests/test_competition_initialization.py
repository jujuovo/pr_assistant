from pathlib import Path

import pytest

from extensions import db
from material_models import MaterialRecord
from legacy_models import Application
from models import Rule, Student, User
from use_cases.competition_initialization import (
    RESET_CONFIRMATION,
    CompetitionInitializationError,
    preview_competition_reset,
    reset_and_initialize_competition_2028,
)
from workflow_models import CompetitionRulePackage, ScoreEntry


def backup_file(tmp_path):
    path = tmp_path / "before-competition-reset.sql"
    path.write_text("-- isolated test backup", encoding="utf-8")
    return path


def add_competition_test_data(env):
    actor = db.session.get(User, env[2]["admin"])
    rule = Rule(
        name="旧竞赛规则", type="academic", sub_type="competition",
        score=1, status="active", faculty_id=actor.faculty_id,
    )
    db.session.add(rule)
    db.session.flush()
    material = MaterialRecord(
        student_id="S1", faculty_id=actor.faculty_id, category="competition",
        year=2028, status="draft", data={}, analysis={},
    )
    db.session.add(material)
    student = Student.query.filter_by(student_id="S1").one()
    application = Application(
        student_id="S1", student_name="张三", faculty_id=actor.faculty_id,
        department_id=student.department_id, major_id=student.major_id,
        application_type="academic", project_name="旧竞赛", rule_id=rule.id,
    )
    db.session.add(application)
    db.session.commit()
    return actor


def test_preview_is_non_mutating_and_reports_exact_scope(env, tmp_path):
    actor = add_competition_test_data(env)
    before = preview_competition_reset()
    result = reset_and_initialize_competition_2028(
        actor, backup_reference=backup_file(tmp_path), confirmation="", dry_run=True
    )
    assert result["preview"] == before
    assert before["competition_materials"] == 1
    assert before["legacy_competition_applications"] == 1
    assert MaterialRecord.query.filter_by(category="competition").count() == 1


def test_execute_requires_backup_and_confirmation(env, tmp_path):
    actor = db.session.get(User, env[2]["admin"])
    with pytest.raises(CompetitionInitializationError) as missing_confirmation:
        reset_and_initialize_competition_2028(
            actor, backup_reference=backup_file(tmp_path), confirmation="wrong", dry_run=False,
            environment_allows_reset=True,
        )
    assert missing_confirmation.value.code == "competition_reset_confirmation_required"
    with pytest.raises(CompetitionInitializationError) as missing_backup:
        reset_and_initialize_competition_2028(
            actor, backup_reference=tmp_path / "missing.sql",
            confirmation=RESET_CONFIRMATION, dry_run=False, environment_allows_reset=True,
        )
    assert missing_backup.value.code == "competition_backup_required"


def test_reset_scope_and_initialization_are_idempotent(env, tmp_path):
    actor = add_competition_test_data(env)
    backup = backup_file(tmp_path)
    first = reset_and_initialize_competition_2028(
        actor, backup_reference=backup, confirmation=RESET_CONFIRMATION, dry_run=False,
        environment_allows_reset=True,
    )
    db.session.commit()
    assert first["created"] is True
    assert MaterialRecord.query.filter_by(category="competition").count() == 0
    assert ScoreEntry.query.filter_by(category="competition").count() == 0
    assert CompetitionRulePackage.query.filter_by(status="current").count() == 1
    second = reset_and_initialize_competition_2028(
        actor, backup_reference=backup, confirmation=RESET_CONFIRMATION, dry_run=False,
        environment_allows_reset=True,
    )
    db.session.commit()
    assert second["created"] is False
    assert second["package"].id == first["package"].id
    assert CompetitionRulePackage.query.filter_by(status="current").count() == 1
