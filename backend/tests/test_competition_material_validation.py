import json
from datetime import date
from pathlib import Path

import pytest

from extensions import db
from material_models import MaterialAttachment
from models import User
from use_cases.competition_rules import load_current_competition_package
from use_cases.cycles import activate_cycle_policy, create_cycle_policy
from use_cases.materials import MaterialUseCaseError, create_material, edit_material, submit_material


def setup_formal_cycle(env):
    admin = db.session.get(User, env[2]['admin'])
    snapshot = json.loads(
        (Path(__file__).parents[1] / 'rules' / 'competition_2028.json').read_text(encoding='utf-8')
    )
    package, _ = load_current_competition_package(admin, snapshot)
    policy, _ = create_cycle_policy(
        admin, 2028, date(2025, 9, 1), date(2028, 8, 31), '2028 推免周期'
    )
    activate_cycle_policy(admin, policy)
    db.session.commit()
    return package, db.session.get(User, env[2]['student'])


def facts(**updates):
    value = {
        'competition_id': 'c09-computer-design', 'project_name': '  作品 甲  ',
        'award_date': '2025-09-01', 'level': 'national',
        'award': 'first_or_above', 'event_year': 2025,
        'participation_mode': 'team', 'team_size': 3, 'personal_rank': 2,
    }
    value.update(updates)
    return value


def test_create_normalizes_and_pins_formal_package(env):
    package, student = setup_formal_cycle(env)
    row = create_material(student, 'competition', {'year': 2028, 'data': facts()})
    db.session.commit()
    assert row.competition_rule_package_id == package.id
    assert row.confirmed_terms['competition_name'] == '中国大学生计算机设计大赛'
    assert row.confirmed_terms['project_name'] == '作品 甲'
    assert row.confirmed_terms['team_size'] == 3
    assert row.analysis['authority'] == 'server'


@pytest.mark.parametrize(
    'updates,code',
    [
        ({'competition_id': 'outside'}, 'unknown_competition'),
        ({'award_date': '2025-08-31'}, 'award_date_ineligible'),
        ({'award_date': '2028-09-01'}, 'award_date_ineligible'),
        ({'team_size': None}, 'team_fields_missing'),
        ({'personal_rank': 4}, 'invalid_team_rank'),
        ({'level': 'provincial'}, 'invalid_competition_level'),
        ({'rule_id': 1}, 'legacy_authority_field_forbidden'),
    ],
)
def test_invalid_competition_facts_are_rejected(env, updates, code):
    _package, student = setup_formal_cycle(env)
    with pytest.raises(MaterialUseCaseError) as error:
        create_material(student, 'competition', {'year': 2028, 'data': facts(**updates)})
    assert error.value.code == code


@pytest.mark.parametrize('award_date', ['2025-09-01', '2028-08-31'])
def test_evidence_period_boundaries_are_inclusive(env, award_date):
    _package, student = setup_formal_cycle(env)
    row = create_material(
        student, 'competition', {'year': 2028, 'data': facts(award_date=award_date)}
    )
    assert row.confirmed_terms['award_date'] == award_date


def test_edit_uses_cas_and_submit_rechecks_package_and_attachment(env):
    package, student = setup_formal_cycle(env)
    row = create_material(student, 'competition', {'year': 2028, 'data': facts()})
    db.session.flush()
    with pytest.raises(MaterialUseCaseError) as conflict:
        edit_material(student, row, row.version + 1, facts(project_name='修改'))
    assert conflict.value.code == 'version_conflict'
    edit_material(student, row, row.version, facts(project_name='修改'))
    with pytest.raises(MaterialUseCaseError) as missing_attachment:
        submit_material(student, row, row.version)
    assert missing_attachment.value.code == 'competition_attachment_required'
    db.session.add(MaterialAttachment(
        record_id=row.id, filename='proof.pdf', stored_name='validation-proof.pdf',
        sha256='b' * 64, size=10,
    ))
    db.session.flush()
    db.session.expire(row, ['attachments'])
    submit_material(student, row, row.version)
    assert row.status == 'submitted'
    assert row.competition_rule_package_id == package.id
