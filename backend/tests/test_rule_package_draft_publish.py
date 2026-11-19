import copy

import pytest

from extensions import db
from models import User
from use_cases.competition_initialization import formal_package_snapshot
from use_cases.competition_rules import (
    copy_competition_package_draft, edit_competition_package_draft, load_current_competition_package,
    publish_competition_package_draft,
)
from workflow_models import CompetitionRulePackage, CompetitionRulePackageCommand


def prepare(env):
    admin = db.session.get(User, env[2]["admin"])
    source, _ = load_current_competition_package(admin, formal_package_snapshot())
    draft, _ = copy_competition_package_draft(
        admin, source_package_id=source.id, target_cycle=2029,
        idempotency_key="publish-copy",
    )
    candidate = copy.deepcopy(draft.snapshot)
    candidate["evidence_period"] = {
        "start": "2026-09-01", "end": "2029-08-31", "boundary": "inclusive"
    }
    edit_competition_package_draft(
        admin, draft, expected_revision=1, snapshot=candidate
    )
    db.session.commit()
    return admin, source, draft


def test_validated_draft_publishes_once_and_replays_idempotently(env):
    app, _client, _users = env
    with app.app_context():
        admin, source, draft = prepare(env)
        published, created = publish_competition_package_draft(
            admin, draft, expected_revision=2, idempotency_key="publish-2029"
        )
        db.session.commit()
        assert created and published.status == "current"
        assert published.current_scope_key == "2029:global"
        assert source.status == "current" and source.current_scope_key == "2028:global"
        replay, created = publish_competition_package_draft(
            admin, published, expected_revision=2, idempotency_key="publish-2029"
        )
        assert not created and replay.id == published.id
        assert CompetitionRulePackage.query.filter_by(cycle_code=2029, status="current").count() == 1
        assert CompetitionRulePackageCommand.query.filter_by(command_type="publish").count() == 1


def test_publish_rejects_invalid_candidate_stale_revision_and_rolls_back(env):
    app, _client, _users = env
    with app.app_context():
        admin, _source, draft = prepare(env)
        with pytest.raises(Exception) as stale:
            publish_competition_package_draft(
                admin, draft, expected_revision=9, idempotency_key="stale-publish"
            )
        assert getattr(stale.value, "code", None) == "version_conflict"
        broken = copy.deepcopy(draft.snapshot)
        broken["catalog"] = []
        draft.snapshot = broken
        draft.digest = CompetitionRulePackage.canonical_digest(broken)
        db.session.flush()
        with pytest.raises(Exception):
            publish_competition_package_draft(
                admin, draft, expected_revision=2, idempotency_key="invalid-publish"
            )
        db.session.rollback(); draft = db.session.get(CompetitionRulePackage, draft.id)
        with pytest.raises(RuntimeError):
            publish_competition_package_draft(
                admin, draft, expected_revision=2, idempotency_key="failed-publish",
                fail_at="after_publish",
            )
        db.session.rollback(); db.session.refresh(draft)
        assert draft.status == "draft" and draft.current_scope_key is None
        assert CompetitionRulePackageCommand.query.filter_by(command_type="publish").count() == 0
