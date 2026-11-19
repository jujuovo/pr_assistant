from extensions import db
from use_cases.competition_review import review_competition_material
from use_cases.competition_rules import send_competition_notification, switch_competition_package
from workflow_models import CompetitionNotificationIntent

from test_competition_rule_correction_preview import _baseline
from test_competition_rule_switch import _changed


def test_send_failure_does_not_roll_back_switch_and_is_retryable(env):
    admin, snapshot, old, row, teacher = _baseline(env)
    review_competition_material(teacher, row, {"version": row.version, "decision": "approve",
        "comment": "一致", "idempotency_key": "notify-approved"})
    switch_competition_package(admin, _changed(snapshot)); db.session.commit()
    intent = CompetitionNotificationIntent.query.one()
    first = send_competition_notification(intent.id, lambda *_: (_ for _ in ()).throw(RuntimeError("offline")))
    db.session.commit()
    assert first["status"] == "pending" and intent.attempts == 1
    assert row.status == "rule_reconfirmation_required" and old.status == "retired"
    calls = []
    second = send_competition_notification(intent.id, lambda *args: calls.append(args))
    db.session.commit()
    assert second["status"] == "sent" and len(calls) == 1 and intent.attempts == 2
    replay = send_competition_notification(intent.id, lambda *args: calls.append(args))
    assert replay["replayed"] and len(calls) == 1


def test_switch_creates_one_intent_without_auto_resubmit_or_rescore(env):
    admin, snapshot, _old, row, _teacher = _baseline(env)
    switch_competition_package(admin, _changed(snapshot))
    assert CompetitionNotificationIntent.query.count() == 1
    assert row.status == "rule_reconfirmation_required"
