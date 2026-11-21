from conftest import login


def test_admin_creates_and_activates_cycle(env):
    app, client, users = env
    login(client, users['admin'])
    assert client.get('/api/workflow/cycles').json == {'items': [], 'active_id': None}
    payload = {'cycle_code': 2028, 'display_name': '2028 推免周期',
               'eligible_award_start_date': '2024-09-01',
               'eligible_award_end_date': '2028-08-31'}
    created = client.post('/api/workflow/cycles', json=payload)
    assert created.status_code == 201
    policy_id = created.json['id']
    assert client.post(f'/api/workflow/cycles/{policy_id}/activate',
                       json={'expected_active_id': None}).status_code == 200
    assert client.get('/api/workflow/cycles').json['active_id'] == policy_id
    assert client.get('/api/workflow/cycles/current').json['cycle_code'] == 2028


def test_cycle_activation_requires_admin_and_current_version(env):
    app, client, users = env
    login(client, users['other'])
    assert client.get('/api/workflow/cycles').status_code == 403
    assert client.post('/api/workflow/cycles', json={}).status_code == 403
    login(client, users['admin'])
    response = client.post('/api/workflow/cycles', json={
        'cycle_code': 2028, 'eligible_award_start_date': '2024-09-01',
        'eligible_award_end_date': '2028-08-31'})
    policy_id = response.json['id']
    assert client.post(f'/api/workflow/cycles/{policy_id}/activate',
                       json={'expected_active_id': 999}).status_code == 409
    assert client.post('/api/workflow/cycles', json={
        'cycle_code': 2029, 'eligible_award_start_date': 'bad',
        'eligible_award_end_date': '2029-08-31'}).status_code == 400
