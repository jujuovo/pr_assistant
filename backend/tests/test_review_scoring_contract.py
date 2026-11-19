import pytest

from extensions import db
from use_cases.review_scoring import ReviewScoringInput, review_scoring_result
from workflow_models import ReviewScoringCommand


def _command(**changes):
    data = dict(
        source_type="material", source_id="12", source_version=3,
        decision="verified", comment="已核验", idempotency_key="review-12-v3",
    )
    data.update(changes)
    return ReviewScoringInput(**data)


def test_review_command_digest_covers_source_version_actor_and_content():
    command = _command()
    assert command.digest(7) == _command().digest(7)
    assert command.digest(7) != _command(source_version=4).digest(7)
    assert command.digest(7) != command.digest(8)
    assert command.digest(7) != _command(comment="不同内容").digest(7)


def test_review_command_rejects_invalid_source_version_and_key():
    with pytest.raises(ValueError):
        _command(source_version=0)
    with pytest.raises(ValueError):
        _command(idempotency_key="")


def test_review_result_contract_has_explicit_double_status_and_actions():
    result = review_scoring_result(
        overall_status="blocked",
        verification_status="verified",
        scoring_status="needs_rule",
        cycle={"cycle_code": 2026, "policy_version": 1},
        eligibility={"status": "eligible"},
        scoring=None,
        snapshot=None,
        allowed_actions=["publish_rule", "retry_scoring"],
    )
    assert set(result) == {
        "overall_status", "verification_status", "scoring_status", "cycle",
        "eligibility", "scoring", "snapshot", "allowed_actions",
    }
    assert result["overall_status"] == "blocked"
    assert result["verification_status"] == "verified"
    assert result["scoring_status"] == "needs_rule"


def test_review_command_idempotency_is_scoped_to_source(env):
    actor_id = env[2]["admin"]
    first = ReviewScoringCommand(
        source_type="material", source_id="12", source_version=3,
        idempotency_key="same-key", request_digest="a" * 64,
        result={"overall_status": "complete"}, created_by=actor_id,
    )
    db.session.add(first)
    db.session.commit()
    db.session.add(ReviewScoringCommand(
        source_type="material", source_id="12", source_version=4,
        idempotency_key="same-key", request_digest="b" * 64,
        result={"overall_status": "complete"}, created_by=actor_id,
    ))
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()
