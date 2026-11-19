from datetime import date

import pytest

from extensions import db
from models import SystemSettings, User
from use_cases.cycles import (
    CycleUseCaseError,
    activate_cycle_policy,
    create_cycle_policy,
    current_cycle_policy,
    switch_cycle_policy,
)


def test_only_admin_can_create_or_activate_cycle(env):
    app, _client, users = env
    with app.app_context():
        teacher = db.session.get(User, users["other"])
        with pytest.raises(CycleUseCaseError) as denied:
            create_cycle_policy(teacher, 2026, date(2023, 9, 1), date(2026, 8, 31))
        assert denied.value.code == "forbidden"
        assert current_cycle_policy(required=False) is None


def test_activation_requires_explicit_switch_and_preserves_current_on_error(env):
    app, _client, users = env
    with app.app_context():
        admin = db.session.get(User, users["admin"])
        first, _ = create_cycle_policy(admin, 2026, date(2023, 9, 1), date(2026, 8, 31))
        activate_cycle_policy(admin, first)
        second, _ = create_cycle_policy(admin, 2027, date(2024, 9, 1), date(2027, 8, 31))
        with pytest.raises(CycleUseCaseError) as conflict:
            activate_cycle_policy(admin, second)
        assert conflict.value.code == "active_cycle_exists"
        assert current_cycle_policy().id == first.id
        switch_cycle_policy(admin, second, expected_active_id=first.id)
        db.session.commit()
        assert current_cycle_policy().id == second.id
        settings = SystemSettings.query.one()
        assert settings.active_cycle_policy_id == second.id
        assert settings.academic_year == "2027"


def test_cycle_policy_creation_is_idempotent(env):
    app, _client, users = env
    with app.app_context():
        admin = db.session.get(User, users["admin"])
        first, created = create_cycle_policy(admin, 2026, date(2023, 9, 1), date(2026, 8, 31))
        second, repeated = create_cycle_policy(admin, 2026, date(2023, 9, 1), date(2026, 8, 31))
        assert created is True and repeated is False and first.id == second.id
