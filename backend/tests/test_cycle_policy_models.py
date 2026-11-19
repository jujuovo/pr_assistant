from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from workflow_models import RecommendationCyclePolicy


def make_policy(user_id, cycle=2026, version=1, active=True):
    start, end = date(2023, 9, 1), date(2026, 8, 31)
    return RecommendationCyclePolicy(
        cycle_code=cycle,
        version=version,
        display_name=str(cycle),
        eligible_award_start_date=start,
        eligible_award_end_date=end,
        boundary="inclusive",
        digest=RecommendationCyclePolicy.canonical_digest(cycle, start, end),
        status="active" if active else "draft",
        active_marker=1 if active else None,
        created_by=user_id,
        activated_by=user_id if active else None,
    )


def test_only_one_cycle_policy_can_be_active(env):
    app, _client, users = env
    with app.app_context():
        db.session.add(make_policy(users["admin"]))
        db.session.commit()
        db.session.add(make_policy(users["admin"], cycle=2027))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        assert RecommendationCyclePolicy.query.filter_by(status="active").count() == 1


def test_cycle_policy_content_is_immutable(env):
    app, _client, users = env
    with app.app_context():
        policy = make_policy(users["admin"])
        db.session.add(policy)
        db.session.commit()
        policy.eligible_award_end_date = date(2027, 8, 31)
        with pytest.raises(ValueError, match="immutable"):
            db.session.commit()
        db.session.rollback()
        stored = db.session.get(RecommendationCyclePolicy, policy.id)
        assert stored.eligible_award_end_date == date(2026, 8, 31)
