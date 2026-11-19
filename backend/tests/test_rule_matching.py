from types import SimpleNamespace

from extensions import db
from models import Rule
from use_cases.rule_versions import publish_rule_version
from use_cases.scoring import match_published_rule


def _publish(name, *, cycle=2026, category="competition", faculty_id=None, score=5):
    rule = Rule(
        name=name, type="academic", sub_type=category, score=score,
        faculty_id=faculty_id, status="active",
    )
    db.session.add(rule)
    version, _ = publish_rule_version(rule, cycle_code=cycle)
    return rule, version


def _row(*, cycle=2026, category="competition", faculty_id=1):
    return SimpleNamespace(year=cycle, category=category, faculty_id=faculty_id)


def test_rule_match_requires_fixed_cycle_category_and_faculty(env):
    app, _client, _users = env
    with app.app_context():
        faculty_id = _row().faculty_id
        _rule, version = _publish("唯一适用", faculty_id=faculty_id)
        _publish("其他周期", cycle=2025, faculty_id=faculty_id)
        _publish("其他类别", category="honor", faculty_id=faculty_id)
        result = match_published_rule(_row(faculty_id=faculty_id))
        assert result["status"] == "matched"
        assert result["version"].id == version.id


def test_rule_match_returns_stable_no_match(env):
    app, _client, _users = env
    with app.app_context():
        _publish("错误周期", cycle=2025)
        assert match_published_rule(_row()) == {
            "status": "no_match", "reason": "no_applicable_published_rule"
        }


def test_rule_match_reports_ambiguous_same_scope_instead_of_first(env):
    app, _client, _users = env
    with app.app_context():
        _one, first = _publish("规则一")
        _two, second = _publish("规则二")
        result = match_published_rule(_row())
        assert result == {
            "status": "ambiguous",
            "reason": "ambiguous_published_rules",
            "rule_version_ids": sorted([first.id, second.id]),
        }


def test_faculty_specific_rule_takes_precedence_over_global(env):
    app, _client, _users = env
    with app.app_context():
        _publish("全局规则")
        _rule, faculty_version = _publish("学院规则", faculty_id=1)
        result = match_published_rule(_row(faculty_id=1))
        assert result["status"] == "matched"
        assert result["version"].id == faculty_version.id
