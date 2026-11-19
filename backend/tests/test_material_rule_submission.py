import pytest

from extensions import db
from material_models import MaterialEvent, MaterialRecord
from models import Rule, User
from use_cases.materials import MaterialUseCaseError, submit_material
from workflow_models import RuleVersion


TERMS = {"competition_name": "蓝桥杯", "award_level": "三等奖",
         "competition_level": "省级", "region": {"any": True},
         "group": "软件类大学B组", "track": None}
MATERIAL_TERMS = {**TERMS, "region": "福建赛区"}


def material(env):
    user = db.session.get(User, env[2]["student"])
    row = MaterialRecord(student_id=user.student_id, faculty_id=user.faculty_id,
                         category="honor", year=2024, status="draft",
                         data={}, analysis={}, normalized_terms=MATERIAL_TERMS,
                         normalization_version="material-terms-v1")
    db.session.add(row); db.session.commit()
    return user, row


def version(faculty_id, *, rule_name="三等奖", terms=TERMS, score=3):
    rule = Rule(name=rule_name, type="academic", sub_type="honor", score=score,
                status="active", faculty_id=faculty_id, match_terms=terms,
                match_schema_version="material-terms-v1")
    db.session.add(rule); db.session.flush()
    snapshot = {"name": rule.name, "sub_type": "honor", "faculty_id": faculty_id,
                "cycle_code": 2026, "score": score, "match_terms": terms,
                "match_schema_version": "material-terms-v1"}
    item = RuleVersion(rule_id=rule.id, version=1, status="published", snapshot=snapshot,
                       digest=RuleVersion.canonical_digest(snapshot),
                       match_terms_digest="digest-" + str(rule.id),
                       match_schema_version="material-terms-v1")
    db.session.add(item); db.session.commit()
    return item


def test_unmapped_save_does_not_pin_cycle_or_create_partial_submission(env, active_cycle):
    user, row = material(env)
    with pytest.raises(MaterialUseCaseError) as caught:
        submit_material(user, row, 1)
    assert caught.value.code == "material_terms_unmapped"
    db.session.rollback(); db.session.refresh(row)
    assert row.status == "draft" and row.rule_version_id is None
    assert row.cycle_policy_version_id is None and row.year == 2024
    assert MaterialEvent.query.filter_by(record_id=row.id).count() == 0


def test_unique_match_atomically_pins_rule_and_cycle(env, active_cycle):
    user, row = material(env); published = version(user.faculty_id)
    submit_material(user, row, 1); db.session.commit()
    assert row.status == "submitted" and row.rule_version_id == published.id
    assert row.year == 2026 and row.cycle_policy_version_id == active_cycle.id


def test_ambiguous_match_rejects_without_partial_write(env, active_cycle):
    user, row = material(env)
    version(user.faculty_id, rule_name="规则一")
    version(user.faculty_id, rule_name="规则二")
    with pytest.raises(MaterialUseCaseError) as caught:
        submit_material(user, row, 1)
    assert caught.value.code == "ambiguous_scoring_rules"
    db.session.rollback(); db.session.refresh(row)
    assert row.status == "draft" and row.rule_version_id is None
    assert row.cycle_policy_version_id is None and row.version == 1
