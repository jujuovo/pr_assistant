from datetime import date

import pytest

from extensions import db
from material_models import MaterialRecord
from legacy_models import Application
from models import Rule, User
from use_cases.cycles import (
    CycleUseCaseError,
    activate_cycle_policy,
    create_cycle_policy,
    pin_application_cycle,
)
from use_cases.materials import submit_material


def activate(env, cycle=2026):
    app, _client, users = env
    admin = db.session.get(User, users["admin"])
    policy, _ = create_cycle_policy(
        admin, cycle, date(2023, 9, 1), date(2026, 8, 31)
    )
    activate_cycle_policy(admin, policy)
    return policy


def application(status="draft"):
    return Application(
        student_id="S1", student_name="张三", faculty_id=1, department_id=1,
        major_id=1, application_type="competition", project_name="蓝桥杯", status=status,
        award_date=date(2024, 4, 1),
    )


def test_application_cycle_is_pinned_once(env):
    app, _client, users = env
    with app.app_context():
        policy = activate(env)
        row = application()
        db.session.add(row)
        pin_application_cycle(row)
        db.session.flush()
        assert row.cycle_code == 2026 and row.cycle_policy_version_id == policy.id
        row.award_date = date(2020, 1, 1)
        assert pin_application_cycle(row).id == policy.id


def test_formal_submission_without_active_cycle_is_blocked(env):
    app, _client, _users = env
    with app.app_context():
        row = application()
        db.session.add(row)
        with pytest.raises(CycleUseCaseError) as missing:
            pin_application_cycle(row)
        assert missing.value.code == "cycle_policy_missing"


def test_material_submit_uses_active_cycle_not_client_year(env):
    app, _client, users = env
    with app.app_context():
        policy = activate(env)
        student = db.session.get(User, users["student"])
        admin = db.session.get(User, users["admin"])
        from use_cases.rule_versions import publish_rule_version
        rule = Rule(name="周期固定荣誉规则", type="academic", sub_type="honor",
                    score=1, max_score=1, faculty_id=1, status="active")
        db.session.add(rule)
        publish_rule_version(rule, published_by=admin, cycle_code=2026)
        row = MaterialRecord(
            student_id="S1", faculty_id=1, category="honor", year=2024,
            status="draft", data={}, analysis={}, version=1,
        )
        db.session.add(row)
        db.session.flush()
        submit_material(student, row, 1)
        assert row.status == "submitted"
        assert row.year == 2026 and row.cycle_policy_version_id == policy.id
