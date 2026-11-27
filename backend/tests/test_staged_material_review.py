"""Real API journeys through both preliminary stages and teacher final review."""
from io import BytesIO
import json
import pytest

from conftest import login
from extensions import db
from models import User
from material_models import MaterialRecord, MaterialEvent
from workflow_models import ScoreEntry, MaterialReviewCommand


def reviewers(env):
    result = {}
    for role in ('reviewer_level1', 'reviewer_level2', 'teacher'):
        for number in (1, 2):
            user = User(username=f'{role}-{number}', name=f'{role}姓名{number}',
                        role=role, password='test', faculty_id=1, status='active')
            db.session.add(user)
            db.session.flush()
            result[role, number] = user.id
    db.session.commit()
    return result


def manual(env):
    login(env[1], env[2]['student'])
    base = '/api/materials/arts_sports/records'
    created = env[1].post(base, data={'year': '2028', 'data': json.dumps({
        'document_type': 'arts_competition', 'project_name': '运动会获奖', 'award_date': '2026-05-01'}),
        'files': (BytesIO(b'proof'), 'proof.png')})
    assert created.status_code == 201, created.json
    url = base + '/' + str(created.json['id'])
    submitted = env[1].post(url + '/submit', json={'version': created.json['version']})
    assert submitted.status_code == 200, submitted.json
    return url, submitted.json


def review(env, users, role, url, row, decision='verified', key=None, number=1):
    login(env[1], users[role, number])
    payload = {'version': row['version'], 'decision': decision, 'comment': '已核对证明',
               'idempotency_key': key or f'{role}:{row["version"]}'}
    return env[1].post(url + '/review', json=payload), payload


def test_full_manual_chain_scoped_queues_history_and_no_early_approval(env):
    users = reviewers(env)
    url, row = manual(env)
    for role, stage in (('reviewer_level1', 1), ('reviewer_level2', 2), ('teacher', 3)):
        for other_role in ('reviewer_level1', 'reviewer_level2', 'teacher'):
            login(env[1], users[other_role, 1])
            queued = env[1].get('/api/materials/arts_sports/records').json['records']
            assert bool(queued) == (other_role == role)
        response, _ = review(env, users, role, url, row)
        assert response.status_code == 200, response.json
        row = response.json
        if stage < 3:
            assert row['status'] == 'submitted' and row['review_stage'] == stage + 1
            assert not ScoreEntry.query.count()
        else:
            assert row['status'] == 'verified'
    login(env[1], env[2]['student'])
    detail = env[1].get(url).json
    reviews = [e for e in detail['review_history'] if e['action'] in {'stage_reviewed', 'reviewed'}]
    assert [r['review_stage'] for r in reviews] == [1, 2, 3]
    assert [r['actor']['id'] for r in reviews] == [users[r, 1] for r in ('reviewer_level1', 'reviewer_level2', 'teacher')]
    for role in ('reviewer_level1', 'reviewer_level2'):
        login(env[1], users[role, 2])
        assert len(env[1].get('/api/materials/arts_sports/records?reviewed=1').json['records']) == 1
    login(env[1], env[2]['other'])
    assert env[1].get(url).status_code == 403
    assert env[1].get(url + '/events').status_code == 403


@pytest.mark.parametrize('return_at', [1, 2, 3])
@pytest.mark.parametrize('return_decision', ['needs_correction', 'rejected'])
def test_any_stage_return_resubmit_starts_from_one_and_keeps_history(env, return_at, return_decision):
    users = reviewers(env)
    url, row = manual(env)
    for stage, role in enumerate(('reviewer_level1', 'reviewer_level2', 'teacher'), 1):
        response, _ = review(env, users, role, url, row,
                             return_decision if stage == return_at else 'verified')
        assert response.status_code == 200, response.json
        row = response.json
        if stage == return_at:
            break
    assert row['status'] == 'needs_correction'
    login(env[1], env[2]['student'])
    detail = env[1].get(url).json
    edited = env[1].patch(url, json={'version': row['version'], 'data': detail['data']})
    assert edited.status_code == 200, edited.json
    submitted = env[1].post(url + '/submit', json={'version': edited.json['version']})
    assert submitted.status_code == 200 and submitted.json['review_stage'] == 1
    assert len(submitted.json['review_history']) >= return_at
    assert not ScoreEntry.query.count()


def test_same_level_any_member_idempotency_stale_version_and_rollback(env):
    users = reviewers(env)
    url, original = manual(env)
    first, payload = review(env, users, 'reviewer_level1', url, original, key='one')
    assert first.status_code == 200, first.json
    again = env[1].post(url + '/review', json=payload)
    assert again.status_code == 200 and again.json['replayed']
    assert MaterialReviewCommand.query.count() == 1
    assert env[1].post(url + '/review', json={**payload, 'comment': 'changed'}).status_code == 409
    other, _ = review(env, users, 'reviewer_level1', url, original, number=2)
    assert other.status_code in {403, 409}
    wrong, _ = review(env, users, 'teacher', url, first.json)
    assert wrong.status_code == 403
    from use_cases.staged_review import review_before_final
    record = db.session.get(MaterialRecord, original['id'])
    second = db.session.get(User, users['reviewer_level2', 2])
    version = record.version
    review_before_final(second, record, {'version': version, 'decision': 'verified', 'comment': '', 'idempotency_key': 'rollback'})
    db.session.rollback()
    db.session.refresh(record)
    assert record.review_stage == 2 and record.version == version
    assert MaterialReviewCommand.query.count() == 1


def test_competition_only_teacher_final_creates_score_and_snapshot(env):
    from test_competition_review_command import _submitted_competition
    from use_cases.competition_review import review_competition_material
    from use_cases.materials import MaterialUseCaseError
    row, final_teacher = _submitted_competition(env)
    row.review_stage = 1
    db.session.commit()
    users = reviewers(env)
    url = f'/api/materials/competition/records/{row.id}'
    current = {'id': row.id, 'version': row.version}
    with pytest.raises(MaterialUseCaseError):
        review_competition_material(final_teacher, row, {'version': row.version,
            'decision': 'approve', 'comment': '', 'idempotency_key': 'bypass'})
    for role in ('reviewer_level1', 'reviewer_level2', 'teacher'):
        response, _ = review(env, users, role, url, current, 'approve')
        assert response.status_code == 200, response.json
        current = response.json
        assert ScoreEntry.query.count() == (1 if role == 'teacher' else 0)
    assert current['status'] == 'scored'
