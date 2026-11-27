import pytest
from conftest import login
from extensions import db
from models import Application, Rule
from workflow_models import ScoreEntry
from test_legacy_application_write_security import draft, url
from test_staged_material_review import reviewers


def command(env, users, role, row, status='approved', number=1):
    login(env[1], users[role, number])
    payload = {'status': status, 'reviewComment': '已核对原件',
               'review_version': row.review_version, 'idempotency_key': f'{role}:{row.review_version}'}
    return env[1].post(url(row) + '/review', json=payload), payload


def test_legacy_chain_records_three_actors_and_student_can_read_history(env):
    users = reviewers(env)
    row = draft(env, status='pending')
    for stage, role in enumerate(('reviewer_level1', 'reviewer_level2', 'teacher'), 1):
        login(env[1], users[role, 1])
        assert len(env[1].get('/api/applications/pending').json) == 1
        result, payload = command(env, users, role, row)
        assert result.status_code == 200, result.json
        repeated = env[1].post(url(row) + '/review', json=payload)
        assert repeated.status_code == 200 and repeated.json['replayed']
        db.session.refresh(row)
        assert len(row.review_history) == stage
        assert row.status == ('approved' if stage == 3 else 'pending')
        if stage < 3:
            assert not ScoreEntry.query.count() and row.final_score is None
    login(env[1], env[2]['student'])
    detail = env[1].get(url(row))
    assert detail.status_code == 200, detail.json
    assert [e['actor']['id'] for e in detail.json['review_history']] == [users[r, 1] for r in ('reviewer_level1', 'reviewer_level2', 'teacher')]
    assert all('digest' not in event for event in detail.json['review_history'])
    login(env[1], env[2]['other'])
    assert env[1].get(url(row)).status_code == 403
    assert env[1].get('/api/applications').json == []


@pytest.mark.parametrize('return_at', [1, 2, 3])
@pytest.mark.parametrize('return_decision', ['needs_correction', 'rejected'])
def test_legacy_return_edit_and_resubmit_resets_stage(env, return_at, return_decision):
    users = reviewers(env)
    row = draft(env, status='pending')
    for stage, role in enumerate(('reviewer_level1', 'reviewer_level2', 'teacher'), 1):
        result, _ = command(env, users, role, row, return_decision if stage == return_at else 'approved')
        assert result.status_code == 200, result.json
        db.session.refresh(row)
        if stage == return_at:
            break
    assert row.status == 'needs_correction'
    login(env[1], env[2]['student'])
    response = env[1].put(url(row), json={'projectName': '修改后的证明', 'status': 'pending'})
    assert response.status_code == 200, response.json
    db.session.refresh(row)
    assert row.review_stage == 1 and len(row.review_history) == return_at
    denied, _ = command(env, users, 'teacher', row)
    assert denied.status_code == 403


def test_legacy_same_stage_competing_reviewer_and_forged_stage_are_blocked(env):
    users = reviewers(env)
    row = draft(env, status='pending')
    first, _ = command(env, users, 'reviewer_level1', row)
    assert first.status_code == 200
    second, _ = command(env, users, 'reviewer_level1', row, number=2)
    assert second.status_code in {403, 409}
    login(env[1], env[2]['student'])
    for field, value in (('review_stage', 3), ('review_version', 100), ('review_history', [])):
        assert env[1].put(url(row), json={field: value}).status_code == 409
    assert len(row.review_history) == 1


def test_linked_material_cannot_be_approved_through_a_second_legacy_chain(env):
    from test_material_review_regressions import linked
    row = linked(env)
    users = reviewers(env)
    response, _ = command(env, users, 'reviewer_level1', row)
    assert response.status_code == 409 and response.json['code'] == 'material_review_route_required'
    assert row.review_stage == 1 and not row.review_history


def test_certificate_return_resubmit_and_teacher_scoring_use_same_three_stages(env, active_cycle):
    from test_certificate_preview import ready
    from models import User
    from material_models import MaterialRecord
    from use_cases.rule_versions import publish_rule_version
    assessment, data = ready(env)
    data['award_date'] = '2026-05-08'
    for fields in data['student_values']:
        fields['date'] = '2026年5月8日'
    publish_rule_version(db.session.get(Rule, data['rule_id']),
        published_by=db.session.get(User, env[2]['admin']), cycle_code=2026)
    db.session.commit()
    confirm_url = f'/api/certificates/applications/{assessment.application_id}/confirm-preview'
    assert env[1].post(confirm_url, json=data).status_code == 200
    users = reviewers(env)
    application = db.session.get(Application, assessment.application_id)
    for role in ('reviewer_level1', 'reviewer_level2', 'teacher'):
        response, _ = command(env, users, role, application,
                              'needs_correction' if role == 'teacher' else 'approved')
        assert response.status_code == 200, response.json
        db.session.refresh(application)
    assert application.status == 'needs_correction' and not ScoreEntry.query.count()
    login(env[1], env[2]['student'])
    db.session.refresh(assessment)
    data['version'] = assessment.version
    response = env[1].post(confirm_url, json=data)
    assert response.status_code == 200, response.json
    db.session.refresh(application)
    material = MaterialRecord.query.filter_by(application_id=application.id).one()
    assert application.review_stage == material.review_stage == 1
    for role in ('reviewer_level1', 'reviewer_level2', 'teacher'):
        response, _ = command(env, users, role, application)
        assert response.status_code == 200, response.json
        db.session.refresh(application)
        assert ScoreEntry.query.count() == (1 if role == 'teacher' else 0)
    assert application.status == 'approved'
    login(env[1], env[2]['student'])
    history = env[1].get(url(application)).json['review_history']
    assert [e['review_stage'] for e in history] == [1, 2, 3, 1, 2, 3]
