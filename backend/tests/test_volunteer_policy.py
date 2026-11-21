from decimal import Decimal
import io
import json
from datetime import date
import pytest
from conftest import login
from domain.volunteer_policy import calculate_hours
from extensions import db
from models import User
from workflow_models import ScoreEntry, StudentScoreSnapshot


@pytest.mark.parametrize('regular,reduced,score', [
    (199,0,'0'), (200,0,'0'), (201,0,'0'), (202,0,'0.05'),
    (220,0,'0.5'), (240,0,'1'), (1000,0,'1'), (0,404,'0.05'),
    (180,44,'0.05'), ('201.9999',0,'0'),
])
def test_official_threshold_halving_and_cap(regular,reduced,score):
    assert Decimal(calculate_hours(regular,reduced)['score']) == Decimal(score)


@pytest.mark.parametrize('value', [-1, True, 'NaN', 'Infinity', '100001', '0.00001', None])
def test_invalid_hours(value):
    with pytest.raises(ValueError):
        calculate_hours(value,0)


@pytest.fixture
def volunteer_env(env):
    from use_cases.cycles import create_cycle_policy, activate_cycle_policy
    admin=db.session.get(User,env[2]['admin'])
    policy,_=create_cycle_policy(admin,2028,date(2024,9,1),date(2028,8,31),'2028')
    activate_cycle_policy(admin,policy)
    db.session.commit()
    return env


def submit_report(env,hours='220',as_of='2028-08-01'):
    client=env[1]
    login(client,env[2]['student'])
    response=client.post('/api/materials/volunteer/records',data={
        'year':'2028','data':json.dumps({'regular_hours':hours,'reduced_hours':'0','award_date':as_of}),
        'files':(io.BytesIO(b'%PDF-1.4 test report'),'report.pdf')})
    assert response.status_code==201,response.json
    row=response.json
    path=f"/api/materials/volunteer/records/{row['id']}"
    response=client.post(path+'/submit',json={'version':row['version']})
    assert response.status_code==200,response.json
    return path,response.json


def approve(env,path,row,key):
    login(env[1],env[2]['admin'])
    return env[1].post(path+'/review',json={'version':row['version'],'decision':'verified',
                                         'comment':'','idempotency_key':key})


def test_each_approved_record_adds_hours_and_updates_one_active_score(volunteer_env):
    env=volunteer_env
    path,row=submit_report(env,'100')
    result=approve(env,path,row,'first')
    assert result.status_code==200,result.json
    assert ScoreEntry.query.filter_by(status='active').one().effective_score == Decimal('0')
    assert approve(env,path,row,'first').status_code==200
    assert ScoreEntry.query.count()==1
    path2,row2=submit_report(env,'102','2028-08-02')
    result=approve(env,path2,row2,'second')
    assert result.status_code==200,result.json
    assert ScoreEntry.query.filter_by(status='active').one().effective_score == Decimal('0.05')
    assert ScoreEntry.query.filter_by(status='active').count()==1
    snapshot=StudentScoreSnapshot.query.filter_by(status='current').one()
    assert snapshot.performance_score == Decimal('0.05')
    assert snapshot.comprehensive_score == Decimal('64.05')
    path3,row3=submit_report(env,'8','2028-07-31')
    assert approve(env,path3,row3,'earlier-event').status_code==200
    assert ScoreEntry.query.filter_by(status='active').one().effective_score == Decimal('0.25')
    assert env[1].get(path3).json['status']=='scored'


def test_individual_reduced_hours_are_halved_in_aggregate(volunteer_env):
    env=volunteer_env
    first, first_row=submit_report(env,'199')
    assert approve(env,first,first_row,'regular').status_code==200
    login(env[1],env[2]['student'])
    response=env[1].post('/api/materials/volunteer/records',data={
        'year':'2028', 'data':json.dumps({'reduced_hours':'6','award_date':'2028-08-02'}),
        'files':(io.BytesIO(b'%PDF-1.4 proof'),'proof.pdf')})
    assert response.status_code==201,response.json
    path=f"/api/materials/volunteer/records/{response.json['id']}"
    submitted=env[1].post(path+'/submit',json={'version':response.json['version']})
    assert submitted.status_code==200,submitted.json
    result=approve(env,path,submitted.json,'reduced')
    assert result.status_code==200,result.json
    assert ScoreEntry.query.filter_by(status='active').one().effective_score==Decimal('0.05')
    assert ScoreEntry.query.filter_by(status='active').count()==1


def test_withdraw_preserves_login_and_rejects_old_version(volunteer_env):
    env=volunteer_env
    path,row=submit_report(env)
    with env[1].session_transaction() as state:
        before=dict(state)
    result=env[1].post(path+'/withdraw',json={'version':row['version']})
    assert result.status_code==200,result.json
    assert result.json['status']=='draft'
    with env[1].session_transaction() as state:
        assert dict(state)==before
    assert env[1].post(path+'/withdraw',json={'version':row['version']}).status_code in (403,409)
    assert env[1].get(path).status_code==200


def test_cross_faculty_review_denied(volunteer_env):
    env=volunteer_env
    path,row=submit_report(env)
    login(env[1],env[2]['other'])
    assert env[1].post(path+'/review',json={'version':row['version'],'decision':'verified','comment':''}).status_code==403
    assert ScoreEntry.query.count()==0


def test_missing_original_cannot_be_approved(volunteer_env):
    from material_models import MaterialRecord
    from services.materials.service import stored_path
    env=volunteer_env
    path,row=submit_report(env)
    evidence=MaterialRecord.query.get(row['id']).attachments[0]
    stored_path(evidence.stored_name).unlink()
    response=approve(env,path,row,'missing-original')
    assert response.status_code==409,response.json
    assert response.json['code']=='original_integrity_failed'
    assert ScoreEntry.query.count()==0


def test_withdrawn_draft_can_be_abandoned_without_losing_evidence(volunteer_env):
    env=volunteer_env
    path,row=submit_report(env)
    draft=env[1].post(path+'/withdraw',json={'version':row['version']}).json
    response=env[1].post(path+'/abandon',json={'version':draft['version']})
    assert response.status_code==200,response.json
    assert response.json['status']=='abandoned'
    assert len(response.json['attachments'])==1
    assert env[1].get('/api/materials/volunteer/records').json['records']==[]
