import json
from datetime import date
from pathlib import Path

from conftest import login
from extensions import db
from models import User
from use_cases.competition_rules import load_current_competition_package
from use_cases.cycles import activate_cycle_policy, create_cycle_policy


def load_package(env):
    actor = db.session.get(User, env[2]['admin'])
    cycle, _ = create_cycle_policy(
        actor, 2028, date(2025, 9, 1), date(2028, 8, 31), '2028 推免周期'
    )
    activate_cycle_policy(actor, cycle)
    snapshot = json.loads(
        (Path(__file__).parents[1] / 'rules' / 'competition_2028.json').read_text(encoding='utf-8')
    )
    package, _ = load_current_competition_package(actor, snapshot)
    db.session.commit()
    return package


def test_catalog_requires_authentication_and_bound_organization(env):
    _app, client, ids = env
    load_package(env)
    assert client.get('/api/materials/competition/catalog').status_code in {401, 403}
    login(client, ids['student'])
    response = client.get('/api/materials/competition/catalog')
    assert response.status_code == 200
    assert len(response.json['items']) == 28


def test_catalog_is_searchable_and_classification_is_server_owned(env):
    _app, client, ids = env
    load_package(env)
    login(client, ids['student'])
    response = client.get('/api/materials/competition/catalog?q=计算机设计')
    assert response.status_code == 200
    assert [item['competition_id'] for item in response.json['items']] == ['c09-computer-design']
    assert response.json['items'][0]['category'] == 'A-'


def test_item_schema_excludes_illegal_options(env):
    _app, client, ids = env
    load_package(env)
    login(client, ids['student'])
    provincial = client.get('/api/materials/competition/catalog/c24-cybersecurity-elite')
    assert provincial.status_code == 200
    assert provincial.json['field_schema']['awards_by_level']['provincial'] == [
        'first_or_above', 'second'
    ]
    assert 'third' not in provincial.json['field_schema']['awards_by_level']['provincial']
    icpc = client.get('/api/materials/competition/catalog/c04-icpc')
    assert icpc.json['field_schema']['formats'] == ['regional', 'world_final']
    assert 'invitation' not in icpc.json['field_schema']['formats']


def test_unknown_catalog_identifier_is_rejected(env):
    _app, client, ids = env
    load_package(env)
    login(client, ids['student'])
    response = client.get('/api/materials/competition/catalog/not-formal')
    assert response.status_code == 404
    assert response.json['code'] == 'unknown_competition'


def test_lanqiao_provincial_awards_follow_policy_without_rewriting_catalog(env):
    package = load_package(env)
    original = json.loads(json.dumps(package.snapshot))
    client = env[1]
    login(client, env[2]['student'])
    detail = client.get('/api/materials/competition/catalog/c15-lanqiao-cup').json
    assert detail['field_schema']['levels'] == ['national', 'provincial']
    assert detail['field_schema']['awards_by_level']['provincial'] == ['first_or_above', 'second']
    context = client.get('/api/materials/competition/context').json
    assert next(item for item in context['catalog']['items'] if item['competition_id'] == 'c15-lanqiao-cup')['levels'] == ['national', 'provincial']
    facts = {'competition_id': 'c15-lanqiao-cup', 'project_name': '蓝桥杯省赛',
             'award_date': '2027-05-01', 'event_year': 2027, 'level': 'provincial',
             'participation_mode': 'individual'}
    for award, expected in [('first_or_above', '0.3333'), ('second', '0.1667')]:
        response = client.post('/api/materials/competition/estimate', json={'data': dict(facts, award=award)})
        assert response.status_code == 200, response.json
        assert response.json['declared_estimate'] == expected
    rejected = client.post('/api/materials/competition/estimate', json={'data': dict(facts, award='third')})
    assert rejected.status_code == 400
    assert rejected.json['code'] == 'provincial_third_award_forbidden'
    saved = client.post('/api/materials/competition/records', json={'year': 2028, 'data': dict(facts, award='second')})
    assert saved.status_code == 201, saved.json
    assert saved.json['data']['level'] == 'provincial'
    assert package.snapshot == original


def test_special_competitions_keep_their_explicit_levels(env):
    load_package(env)
    login(env[1], env[2]['student'])
    for competition in ['c04-icpc', 'c05-ccpc', 'c28-ccf-csp']:
        response = env[1].get('/api/materials/competition/catalog/' + competition)
        assert response.json['field_schema']['levels'] == ['national']
