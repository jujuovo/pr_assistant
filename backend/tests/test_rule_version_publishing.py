import pytest

from extensions import db
from models import Rule
from use_cases.rule_versions import RulePublishingError, publish_rule_version
from workflow_models import RuleVersion


def test_same_rule_content_idempotently_reuses_published_version(env):
    rule = Rule(name="蓝桥杯一等奖", type="academic", sub_type="competition", score=5)
    db.session.add(rule)
    first, created_first = publish_rule_version(rule)
    second, created_second = publish_rule_version(rule)
    db.session.commit()

    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    assert RuleVersion.query.filter_by(rule_id=rule.id).count() == 1


def test_changed_rule_content_creates_new_immutable_version(env):
    rule = Rule(name="蓝桥杯一等奖", type="academic", sub_type="competition", score=5)
    db.session.add(rule)
    first, _ = publish_rule_version(rule)
    db.session.commit()

    rule.score = 4
    second, created = publish_rule_version(rule)
    db.session.commit()

    assert created is True
    assert second.version == 2
    assert first.snapshot["score"] == 5
    assert second.snapshot["score"] == 4
    first.snapshot = {"score": 999}
    with pytest.raises(ValueError, match="immutable"):
        db.session.commit()
    db.session.rollback()


def test_structured_mapping_is_frozen_in_published_version(env):
    terms = {
        "competition_name": "蓝桥杯",
        "award_level": "三等奖", "competition_level": "省级",
        "region": "福建赛区", "group": "软件类大学B组", "track": None,
    }
    rule = Rule(
        name="蓝桥杯省级三等奖", type="academic", sub_type="competition", score=2,
        match_terms=terms, match_schema_version="material-terms-v1",
    )
    db.session.add(rule)
    first, created = publish_rule_version(rule, cycle_code=2026)
    db.session.commit()
    assert created
    assert first.snapshot["match_terms"] == terms
    assert first.snapshot["match_schema_version"] == "material-terms-v1"
    assert first.match_terms_digest and len(first.match_terms_digest) == 64

    rule.match_terms = {**terms, "award_level": "二等奖"}
    second, created = publish_rule_version(rule, cycle_code=2026)
    db.session.commit()
    assert created and second.version == 2
    assert first.snapshot["match_terms"]["award_level"] == "三等奖"
    assert second.snapshot["match_terms"]["award_level"] == "二等奖"


def test_enabling_rule_through_api_publishes_current_content(env):
    app, client, _users = env
    from blueprints.rule_bp import rule_bp

    app.register_blueprint(rule_bp)
    rule = Rule(
        name="待启用规则", type="academic", sub_type="competition", score=5,
        status="disabled",
    )
    db.session.add(rule)
    db.session.commit()

    response = client.patch(f"/api/rules/{rule.id}/status")
    assert response.status_code == 200
    version = RuleVersion.query.filter_by(rule_id=rule.id).one()
    assert version.version == 1
    assert version.snapshot["score"] == 5

    client.patch(f"/api/rules/{rule.id}/status")
    response = client.patch(f"/api/rules/{rule.id}/status")
    assert response.status_code == 200
    assert RuleVersion.query.filter_by(rule_id=rule.id).count() == 1


def _structured_rule(name, faculty_id, award_level="三等奖"):
    return Rule(
        name=name, type="academic", sub_type="competition", score=2,
        faculty_id=faculty_id, match_schema_version="material-terms-v1",
        match_terms={
            "competition_name": "蓝桥杯", "award_level": award_level,
            "competition_level": "省级", "region": {"any": True},
            "group": "软件类大学B组", "track": None,
        },
    )


def test_overlapping_structured_rule_is_rejected_without_mutating_published(env):
    first_rule = _structured_rule("学院三等奖", 1)
    db.session.add(first_rule)
    first, _ = publish_rule_version(first_rule, cycle_code=2026)
    db.session.commit()
    second_rule = _structured_rule("全校三等奖", None)
    db.session.add(second_rule)
    with pytest.raises(RulePublishingError) as error:
        publish_rule_version(second_rule, cycle_code=2026)
    assert error.value.code == "ambiguous_scoring_rules"
    assert error.value.conflicts == [first.id]
    db.session.rollback()
    assert RuleVersion.query.count() == 1


def test_disjoint_faculties_and_award_levels_can_publish(env):
    rules = [
        _structured_rule("一院三等奖", 1),
        _structured_rule("二院三等奖", 2),
        _structured_rule("一院二等奖", 1, award_level="二等奖"),
    ]
    db.session.add_all(rules)
    versions = [publish_rule_version(rule, cycle_code=2026)[0] for rule in rules]
    db.session.commit()
    assert [row.version for row in versions] == [1, 1, 1]


def test_structured_rule_requires_complete_explicit_dimensions(env):
    rule = _structured_rule("缺字段", 1)
    rule.match_terms = {"competition_name": "蓝桥杯", "award_level": "三等奖"}
    db.session.add(rule)
    with pytest.raises(RulePublishingError, match="完整匹配维度"):
        publish_rule_version(rule, cycle_code=2026)
