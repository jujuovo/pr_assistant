from extensions import db
from use_cases.competition_review import review_competition_material
from use_cases.competition_rules import switch_competition_package
from use_cases.materials import reconfirm_competition_rule
from workflow_models import ScoreEntry

from test_competition_rule_correction_preview import _baseline
from test_competition_rule_switch import _changed


def test_reconfirmation_creates_new_submitted_version_and_preserves_history(env):
    admin, snapshot, old, row, teacher = _baseline(env)
    student = row.student_id
    old_score, _ = review_competition_material(teacher, row, {"version": row.version,
        "decision": "approve", "comment": "一致", "idempotency_key": "old-approval"})
    switch_competition_package(admin, _changed(snapshot))
    source_version = row.version
    replacement = reconfirm_competition_rule(
        db.session.get(type(admin), env[2]["student"]), row, source_version,
        {key: value for key, value in row.confirmed_terms.items() if key in {
            "competition_id", "project_name", "award_date", "level", "award",
            "event_year", "participation_mode", "team_size", "personal_rank",
            "event_format", "csp_percentile", "group", "track"}}, True,
    )
    assert replacement.id != row.id and replacement.supersedes_record_id == row.id
    assert replacement.status == "submitted"
    assert replacement.competition_rule_package_id != old.id
    assert row.status == "rule_reconfirmation_required"
    assert ScoreEntry.query.filter_by(status="active").count() == 0

    review_competition_material(teacher, replacement, {"version": replacement.version,
        "decision": "approve", "comment": "重新核验一致", "idempotency_key": "new-approval"})
    assert replacement.status == "scored"
    assert ScoreEntry.query.filter_by(status="active").count() == 1
    assert ScoreEntry.query.filter_by(status="invalidated").count() == 1
    assert ScoreEntry.query.filter_by(student_id=student).count() == 2
