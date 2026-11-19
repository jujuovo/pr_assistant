import copy

import pytest

from conftest import login
from extensions import db
from models import User
from use_cases.competition_initialization import formal_package_snapshot
from use_cases.competition_rules import copy_competition_package_draft, load_current_competition_package
from workflow_models import CompetitionRulePackage, CompetitionRulePackageCommand


def seed_2028(env):
    admin = db.session.get(User, env[2]["admin"])
    package, _ = load_current_competition_package(admin, formal_package_snapshot())
    db.session.commit()
    return admin, package


def test_2028_to_2029_copy_is_deep_auditable_and_idempotent(env):
    app, _client, _users = env
    with app.app_context():
        admin, source = seed_2028(env)
        original = copy.deepcopy(source.snapshot)
        draft, created = copy_competition_package_draft(
            admin, source_package_id=source.id, target_cycle=2029,
            idempotency_key="copy-2029",
        )
        db.session.commit()
        assert created and draft.status == "draft" and draft.current_scope_key is None
        assert draft.source_package_id == source.id and draft.source_digest == source.digest
        assert draft.source_summary["version"] == source.version
        assert draft.snapshot is not source.snapshot
        assert draft.snapshot["cycle_code"] == 2029
        assert source.snapshot == original and source.cycle_code == 2028
        replay, created = copy_competition_package_draft(
            admin, source_package_id=source.id, target_cycle=2029,
            idempotency_key="copy-2029",
        )
        assert not created and replay.id == draft.id
        assert CompetitionRulePackage.query.filter_by(cycle_code=2029).count() == 1
        assert CompetitionRulePackageCommand.query.count() == 1


def test_copy_rejects_non_admin_and_rolls_back_injected_failure(env):
    app, _client, users = env
    with app.app_context():
        admin, source = seed_2028(env)
        student = db.session.get(User, users["student"])
        with pytest.raises(Exception) as forbidden:
            copy_competition_package_draft(
                student, source_package_id=source.id, target_cycle=2029,
                idempotency_key="student-copy",
            )
        assert getattr(forbidden.value, "code", None) == "forbidden"
        with pytest.raises(RuntimeError):
            copy_competition_package_draft(
                admin, source_package_id=source.id, target_cycle=2029,
                idempotency_key="failed-copy", fail_at="after_draft",
            )
        db.session.rollback()
        assert CompetitionRulePackage.query.filter_by(cycle_code=2029).count() == 0
        assert CompetitionRulePackageCommand.query.count() == 0
