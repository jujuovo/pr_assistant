import copy

from extensions import db
from models import User
from use_cases.competition_initialization import formal_package_snapshot
from use_cases.competition_rules import (
    copy_competition_package_draft, edit_competition_package_draft,
    load_current_competition_package, publish_competition_package_draft,
)
from workflow_models import CompetitionNotificationIntent


def test_future_empty_cycle_publish_creates_no_false_reconfirmation(env):
    app, _client, users = env
    with app.app_context():
        admin = db.session.get(User, users["admin"])
        source, _ = load_current_competition_package(admin, formal_package_snapshot())
        draft, _ = copy_competition_package_draft(
            admin, source_package_id=source.id, target_cycle=2029,
            idempotency_key="future-copy",
        )
        candidate = copy.deepcopy(draft.snapshot)
        candidate["evidence_period"] = {
            "start": "2026-09-01", "end": "2029-08-31", "boundary": "inclusive"
        }
        edit_competition_package_draft(
            admin, draft, expected_revision=1, snapshot=candidate
        )
        publish_competition_package_draft(
            admin, draft, expected_revision=2, idempotency_key="future-publish"
        )
        db.session.commit()
        assert CompetitionNotificationIntent.query.count() == 0
