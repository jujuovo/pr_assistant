"""Score-source detail scope, compatibility and original proof reuse."""
from datetime import datetime
import pytest
from conftest import login
from extensions import db
from models import User,Student
from material_models import MaterialRecord,MaterialEvent
from workflow_models import ScoreEntry,StudentScoreSnapshot
from test_ocr_workflow_integration import queued_material,Provider,picture,setup_formal,facts
from services.competition_ocr.worker import run_one_ocr


def approved(env):
    row,path,job=queued_material(env)
    assert run_one_ocr(env[0],Provider())
    submitted=env[1].post(path+'/submit',json={'version':row['version']}).json
    teacher=User(username='detail_teacher',name='教师',password='test',role='teacher',status='active',faculty_id=row['faculty_id'])
    db.session.add(teacher);db.session.commit();login(env[1],teacher.id)
    result=env[1].post(path+'/review',json={'version':submitted['version'],'decision':'approve','comment':'','ocr_confirmed':True,'idempotency_key':'detail-approve'})
    assert result.status_code==200,result.json
    return row,teacher


def test_student_opens_actual_project_original_ocr_and_review_history_without_writes(env):
    row,teacher=approved(env);login(env[1],env[2]['student'])
    before=(MaterialEvent.query.count(),ScoreEntry.query.count(),StudentScoreSnapshot.query.count())
    version=db.session.get(MaterialRecord,row['id']).version
    response=env[1].get(f"/api/workflow/students/S1/score-sources/material/{row['id']}?year=2028")
    assert response.status_code==200,response.json
    data=response.json
    assert data['title']=='测试作品' and data['status']=='scored'
    assert data['data']['project_name']=='测试作品'
    assert data['ocr_raw_terms']['report']['fields']['participants']==['张三']
    assert data['history'][-1]['action']=='competition_approved'
    assert data['history'][-1]['comment']==''
    assert env[1].get(data['attachments'][0]['url']+'?inline=1').data==picture()
    assert (MaterialEvent.query.count(),ScoreEntry.query.count(),StudentScoreSnapshot.query.count())==before
    assert db.session.get(MaterialRecord,row['id']).version==version


def test_source_endpoint_enforces_student_owner_faculty_year_and_visible_source(env):
    row,teacher=approved(env)
    path=f"/api/workflow/students/S1/score-sources/material/{row['id']}?year=2028"
    login(env[1],env[2]['other']);assert env[1].get(path).status_code==403
    original=Student.query.filter_by(student_id='S1').one()
    another=Student(student_id='S2',student_name='别的同学',faculty_id=original.faculty_id,department_id=original.department_id,major_id=original.major_id)
    db.session.add(another);db.session.flush()
    account=User(username='detail_other_student',name='别的同学',password='test',role='student',status='active',student_id='S2',faculty_id=another.faculty_id)
    db.session.add(account);db.session.commit();login(env[1],account.id)
    assert env[1].get(path).status_code==403
    assert env[1].get(path.replace('/students/S1/','/students/S2/')).status_code==404
    login(env[1],env[2]['student'])
    assert env[1].get(path.replace('year=2028','year=2027')).status_code==404
    assert env[1].get(path.replace('/material/','/unknown/')).status_code==404
    assert env[1].get(path.replace(str(row['id'])+'?','9999?')).status_code==404
    for year in ['bad','0','2101','']:
        assert env[1].get(path.replace('year=2028','year='+year)).status_code==400
    login(env[1],teacher.id);assert env[1].get(path).status_code==200
    login(env[1],env[2]['admin']);assert env[1].get(path).status_code==200


def test_private_draft_not_in_score_explanation_has_no_detail_entry(env):
    setup_formal(env);login(env[1],env[2]['student'])
    row=env[1].post('/api/materials/competition/records',json={'year':2028,'data':facts()}).json
    assert env[1].get(f"/api/workflow/students/S1/score-sources/material/{row['id']}?year=2028").status_code==404


@pytest.mark.parametrize('source_type',['legacy_application','volunteer_automation'])
def test_legacy_score_opens_corresponding_application_and_review_time(env,source_type):
    from test_legacy_application_adapter import _application,_rule_with_version
    from use_cases.scoring import adapt_legacy_application
    student=Student.query.filter_by(student_id='S1').one();rule,_=_rule_with_version()
    application=_application(student,rule,project_name='已审核科研项目',description='研究说明',review_comment='已核对',reviewed_at=datetime(2026,5,1,14,30,20),files=[{'name':'proof.png','path':'/uploads/files/proof.png'}])
    adapt_legacy_application(application,source_type=source_type);db.session.commit();login(env[1],env[2]['student'])
    response=env[1].get(f"/api/workflow/students/S1/score-sources/{source_type}/{application.id}?year=2026")
    assert response.status_code==200,response.json
    assert response.json['title']=='已审核科研项目'
    assert response.json['data']['description']=='研究说明'
    assert response.json['history'][0]['created_at']=='2026-05-01T14:30:20+08:00'
    assert response.json['attachments'][0]['url']=='/uploads/files/proof.png'
