import copy

import pytest

from extensions import db
from models import User
from use_cases.competition_initialization import formal_package_snapshot
from use_cases.competition_rules import (
    copy_competition_package_draft, edit_competition_package_draft,
    load_current_competition_package,
)
from workflow_models import CompetitionRulePackageRevision


def prepare(env):
    admin = db.session.get(User, env[2]["admin"])
    source, _ = load_current_competition_package(admin, formal_package_snapshot())
    draft, _ = copy_competition_package_draft(
        admin, source_package_id=source.id, target_cycle=2029,
        idempotency_key="copy-edit-2029",
    )
    db.session.commit()
    return admin, source, draft


def test_draft_edit_uses_revision_cas_and_preserves_prior_content(env):
    app, _client, _users = env
    with app.app_context():
        admin, source, draft = prepare(env)
        candidate = copy.deepcopy(draft.snapshot)
        candidate["policy"]["competition_max_count"] = 4
        edited, changed = edit_competition_package_draft(
            admin, draft, expected_revision=1, snapshot=candidate
        )
        db.session.commit()
        assert changed and edited.draft_revision == 2
        revisions = CompetitionRulePackageRevision.query.filter_by(
            package_id=draft.id
        ).order_by(CompetitionRulePackageRevision.revision).all()
        assert [row.revision for row in revisions] == [1, 2]
        assert revisions[0].snapshot["policy"]["competition_max_count"] == 3
        assert revisions[1].snapshot["policy"]["competition_max_count"] == 4
        assert source.snapshot["policy"]["competition_max_count"] == 3
        with pytest.raises(Exception) as conflict:
            edit_competition_package_draft(
                admin, draft, expected_revision=1, snapshot=candidate
            )
        assert getattr(conflict.value, "code", None) == "version_conflict"


def test_published_package_edit_is_rejected_and_draft_failure_rolls_back(env):
    app, _client, _users = env
    with app.app_context():
        admin, source, draft = prepare(env)
        with pytest.raises(Exception) as immutable:
            edit_competition_package_draft(
                admin, source, expected_revision=1, snapshot=source.snapshot
            )
        assert getattr(immutable.value, "code", None) == "package_immutable"
        before = copy.deepcopy(draft.snapshot)
        candidate = copy.deepcopy(before); candidate["description"] = "2029 edited"
        with pytest.raises(RuntimeError):
            edit_competition_package_draft(
                admin, draft, expected_revision=1, snapshot=candidate,
                fail_at="after_revision",
            )
        db.session.rollback(); db.session.refresh(draft)
        assert draft.draft_revision == 1 and draft.snapshot == before
        assert CompetitionRulePackageRevision.query.filter_by(package_id=draft.id).count() == 1
