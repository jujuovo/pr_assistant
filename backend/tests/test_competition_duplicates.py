import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from material_models import MaterialAttachment, MaterialRecord
from models import User
from use_cases.competition_rules import load_current_competition_package
from use_cases.cycles import activate_cycle_policy, create_cycle_policy
from use_cases.materials import MaterialUseCaseError, create_material, submit_material


def setup_cycle(env, mutate=None):
    admin = db.session.get(User, env[2]['admin'])
    snapshot = json.loads(
        (Path(__file__).parents[1] / 'rules' / 'competition_2028.json').read_text(encoding='utf-8')
    )
    if mutate:
        mutate(snapshot)
    load_current_competition_package(admin, snapshot)
    policy, _ = create_cycle_policy(
        admin, 2028, date(2025, 9, 1), date(2028, 8, 31), '2028 推免周期'
    )
    activate_cycle_policy(admin, policy)
    db.session.commit()


def facts(**updates):
    value = {
        'competition_id': 'c09-computer-design', 'project_name': '作品甲',
        'award_date': '2027-05-01', 'level': 'national',
        'award': 'first_or_above', 'event_year': 2027,
        'participation_mode': 'individual',
    }
    value.update(updates)
    return value


def attach(row, suffix):
    db.session.add(MaterialAttachment(
        record_id=row.id, filename='proof.pdf', stored_name=f'duplicate-{suffix}.pdf',
        sha256=suffix[0] * 64, size=10,
    ))
    db.session.flush()
    db.session.expire(row, ['attachments'])


def submit(student, payload, suffix):
    row = create_material(student, 'competition', {'year': 2028, 'data': payload})
    db.session.flush(); attach(row, suffix)
    submit_material(student, row, row.version)
    db.session.flush()
    return row


def test_exact_duplicate_for_same_student_and_cycle_is_rejected(env):
    setup_cycle(env)
    student = db.session.get(User, env[2]['student'])
    submit(student, facts(), 'a')
    with pytest.raises(MaterialUseCaseError) as error:
        submit(student, facts(), 'b')
    assert error.value.code == 'duplicate_submission'


def test_same_project_with_different_award_fact_is_preserved_for_aggregation(env):
    setup_cycle(env)
    student = db.session.get(User, env[2]['student'])
    first = submit(student, facts(award='first_or_above'), 'c')
    second = submit(student, facts(award='second'), 'd')
    assert first.competition_duplicate_digest != second.competition_duplicate_digest
    assert first.competition_work_group_key == second.competition_work_group_key


def test_same_project_name_at_different_levels_is_not_an_exact_duplicate(env):
    def allow_provincial(snapshot):
        item = next(value for value in snapshot['catalog'] if value['competition_id'] == 'c09-computer-design')
        item['levels'].append('provincial')

    setup_cycle(env, mutate=allow_provincial)
    student = db.session.get(User, env[2]['student'])
    national = submit(student, facts(level='national'), 'g')
    provincial = submit(student, facts(level='provincial'), 'h')
    assert national.competition_duplicate_digest != provincial.competition_duplicate_digest
    assert national.competition_work_group_key == provincial.competition_work_group_key


def test_database_unique_index_closes_concurrent_duplicate_race(env):
    setup_cycle(env)
    student = db.session.get(User, env[2]['student'])
    first = submit(student, facts(), 'e')
    duplicate = MaterialRecord(
        student_id=first.student_id, faculty_id=first.faculty_id,
        category='competition', year=first.year, status='submitted',
        data=dict(first.data), analysis={},
        competition_rule_package_id=first.competition_rule_package_id,
        competition_duplicate_digest=first.competition_duplicate_digest,
    )
    db.session.add(duplicate)
    with pytest.raises(IntegrityError):
        db.session.flush()


def test_identical_fact_for_different_student_is_not_globally_blocked(env):
    setup_cycle(env)
    student = db.session.get(User, env[2]['student'])
    first = submit(student, facts(), 'f')
    clone = MaterialRecord(
        student_id='OTHER', faculty_id=first.faculty_id,
        category='competition', year=first.year, status='submitted',
        data=dict(first.data), analysis={},
        competition_rule_package_id=first.competition_rule_package_id,
        competition_duplicate_digest=first.competition_duplicate_digest,
    )
    # The index key includes student_id; a foreign-key fixture is unnecessary for
    # this model-level assertion because SQLite tests do not enable FK enforcement.
    db.session.add(clone)
    db.session.flush()
