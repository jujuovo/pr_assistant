"""Three-role integration: local OCR, formal authority, manual evidence and score feedback."""
import copy
import io
import json
from datetime import date
from pathlib import Path

import pytest
from PIL import Image
from conftest import login
from extensions import db
from models import Application, User
from material_models import CompetitionOcrJob, MaterialRecord
from ocr_models import OCRJob, OCRMaterialLink
from workflow_models import CompetitionRulePackage, RecommendationCyclePolicy, ScoreEntry, StudentScoreSnapshot
from services.competition_ocr.worker import run_one_ocr


def setup_formal(env):
    from use_cases.competition_rules import load_current_competition_package
    from use_cases.cycles import create_cycle_policy, activate_cycle_policy
    admin = db.session.get(User, env[2]["admin"])
    if not CompetitionRulePackage.query.filter_by(cycle_code=2028,status="current").first():
        snapshot = json.loads((Path(__file__).parents[1]/"rules/competition_2028.json").read_text(encoding="utf-8"))
        load_current_competition_package(admin,snapshot)
    if not RecommendationCyclePolicy.query.filter_by(status="active",cycle_code=2028).first():
        policy,_ = create_cycle_policy(admin,2028,date(2025,9,1),date(2028,8,31),"2028 推免周期")
        activate_cycle_policy(admin,policy)
    db.session.commit()


class Provider:
    def predict(self,path):
        texts=["中国大学生计算机设计大赛","参赛学生：张三","《测试作品》","二等奖","2026年5月8日"]
        return {"rec_texts":texts,"rec_scores":[.99]*len(texts),"rec_polys":[[[10,i*40],[400,i*40],[400,i*40+20],[10,i*40+20]] for i in range(len(texts))]}


def facts():
    return {"competition_id":"c09-computer-design","project_name":"测试作品","award_date":"2026-05-08",
            "level":"national","award":"second","event_year":2026,"participation_mode":"individual"}


def picture():
    image=io.BytesIO();Image.new("RGB",(800,800),"white").save(image,format="PNG");return image.getvalue()


def queued_material(env):
    setup_formal(env);login(env[1],env[2]["student"])
    row=env[1].post('/api/materials/competition/records',json={"year":2028,"data":facts()}).json
    assert "id" in row,row
    path=f"/api/materials/competition/records/{row['id']}"
    row=env[1].post(path+'/attachments',data={"version":str(row['version']),"files":(io.BytesIO(picture()),"proof.png")}).json
    result=env[1].post(path+'/ocr',json={"version":row['version']})
    assert result.status_code==201,result.json
    return row,path,result.json


def test_material_page_ocr_reaches_real_worker_then_teacher_scoring(env):
    row,path,job=queued_material(env)
    assert db.session.get(OCRJob,job['job_id']).status=='queued'
    before=copy.deepcopy(db.session.get(MaterialRecord,row['id']).confirmed_terms)
    assert run_one_ocr(env[0],Provider())
    result=env[1].get(path+'/ocr/'+job['job_id']).json
    assert result['status']=='completed',result
    assert result['raw_result']['mapping']['data']['evidence']['participants']==['张三']
    assert env[1].get(result['raw_result']['artifact_urls']['original']).data==picture()
    assert before==db.session.get(MaterialRecord,row['id']).confirmed_terms
    data=facts()|{"evidence":result['raw_result']['mapping']['data']['evidence']}
    confirmed=env[1].post(f"/api/ocr/jobs/{job['job_id']}/confirm-material",json={"material_record_id":row['id'],"version":row['version'],"data":data})
    assert confirmed.status_code==200,confirmed.json
    material=confirmed.json['material'];assert material['application_id'] is None
    submitted=env[1].post(path+'/submit',json={"version":material['version']})
    assert submitted.status_code==200,submitted.json
    teacher=User(username='ocr_teacher',password='test',name='教师',role='teacher',status='active',faculty_id=material['faculty_id'])
    db.session.add(teacher);db.session.commit();login(env[1],teacher.id)
    context=env[1].get(path+'/review-context')
    assert context.status_code==200,context.json
    assert context.json['ocr_links'][0]['job_id']==job['job_id']
    approved=env[1].post(path+'/review',json={"version":submitted.json['version'],"decision":"approve","comment":"原件与学生确认内容一致","idempotency_key":"ocr-integration-approve","ocr_confirmed":True})
    assert approved.status_code==200,approved.json
    assert ScoreEntry.query.count()==1 and StudentScoreSnapshot.query.count()==1
    assert Application.query.count()==0 and OCRMaterialLink.query.count()==1
    assert env[1].post(path+'/review',json={"version":submitted.json['version'],"decision":"approve","comment":"原件与学生确认内容一致","idempotency_key":"ocr-integration-approve","ocr_confirmed":True}).status_code==200
    assert ScoreEntry.query.count()==1


@pytest.mark.parametrize('action',['cancel','edit'])
def test_late_ocr_cannot_overwrite_or_confirm_changed_material(env,action):
    row,path,job=queued_material(env)
    if action=='cancel':
        response=env[1].post(path+'/ocr/'+job['job_id']+'/cancel',json={"version":row['version']})
    else:
        response=env[1].patch(path,json={"version":row['version'],"data":facts()|{"project_name":"学生已修改"}})
    assert response.status_code==200,response.json
    assert run_one_ocr(env[0],Provider())
    lifecycle=CompetitionOcrJob.query.filter_by(job_id=job['job_id']).one()
    assert lifecycle.status=='ignored'
    material=db.session.get(MaterialRecord,row['id'])
    assert material.ocr_raw_terms is None
    confirm=env[1].post(f"/api/ocr/jobs/{job['job_id']}/confirm-material",json={"material_record_id":row['id'],"version":material.version,"data":facts()})
    assert confirm.status_code==409 and OCRMaterialLink.query.count()==0


def test_csp_requires_official_percentile_instead_of_guessing_from_total(env):
    setup_formal(env)
    from services.competition_ocr.mapping import suggestions
    from test_ocr_material_fields import CSP
    mapped=suggestions('csp',{'fields':CSP})
    assert mapped['material_category']=='competition'
    assert 'csp_percentile' in mapped['missing_fields'] and 'csp_percentile' not in mapped['data']
    assert mapped['data']['evidence']['score']==260
    login(env[1],env[2]['student'])
    data=facts()|{"competition_id":"c28-ccf-csp","evidence":mapped['data']['evidence']}
    response=env[1].post('/api/materials/competition/records',json={"year":2028,"data":data})
    assert response.status_code==400 and response.json['code']=='csp_percentile_required'


def test_outside_catalog_material_verifies_without_score_or_application(env):
    from test_ocr_material_fields import prepared_job,AWARD,completed_data
    job_id,_=prepared_job(env,'software-design',AWARD)
    response=env[1].post(f'/api/ocr/jobs/{job_id}/confirm-material',json={"year":2026,"data":completed_data('software-design',AWARD)})
    assert response.status_code==201,response.json
    row=response.json['material'];assert row['category']=='competition_evidence' and row['manual_only']
    path=f"/api/materials/competition_evidence/records/{row['id']}"
    submitted=env[1].post(path+'/submit',json={"version":row['version']})
    assert submitted.status_code==200,submitted.json
    login(env[1],env[2]['admin'])
    reviewed=env[1].post(path+'/review',json={"version":submitted.json['version'],"decision":"verified","comment":"人工核验已完成"})
    assert reviewed.status_code==200,reviewed.json
    assert ScoreEntry.query.count()==StudentScoreSnapshot.query.count()==Application.query.count()==0


def test_missing_attachment_or_unsupported_project_never_leaves_queued_jobs(env):
    setup_formal(env);login(env[1],env[2]['student'])
    row=env[1].post('/api/materials/competition/records',json={"year":2028,"data":facts()}).json
    response=env[1].post(f"/api/materials/competition/records/{row['id']}/ocr",json={"version":row['version']})
    assert response.status_code==400,response.json
    assert OCRJob.query.count()==CompetitionOcrJob.query.count()==0


@pytest.mark.parametrize('result',[None,{'scoring':None}])
def test_current_score_handles_null_historical_review_results(env,result):
    setup_formal(env);login(env[1],env[2]['student'])
    row=env[1].post('/api/materials/competition/records',json={"year":2028,"data":facts()}).json
    from workflow_models import MaterialReviewCommand
    db.session.add(MaterialReviewCommand(record_id=row['id'],idempotency_key='legacy-null',request_digest='a'*64,
                                        result=result,created_by=env[2]['student']))
    db.session.commit()
    response=env[1].get('/api/workflow/students/S1/score/current')
    assert response.status_code==200,response.json
    assert response.json['status']=='no_authoritative_snapshot'
    assert response.json['comprehensive_score'] is None


def test_legacy_new_preview_is_disabled_in_integrated_application(env):
    env[0].config['ALLOW_LEGACY_CERTIFICATE_PREVIEWS']=False
    login(env[1],env[2]['student'])
    response=env[1].post('/api/certificates/previews',data={'files':(io.BytesIO(picture()),'proof.png')})
    assert response.status_code==409 and response.json['code']=='competition_material_route_required'
    assert Application.query.count()==0


def test_manual_opt_out_preserves_provincial_evidence_without_catalog_override(env):
    from test_ocr_material_fields import prepared_job,LANQIAO
    from services.competition_ocr.mapping import raw_suggestions
    job_id,_=prepared_job(env,'lanqiao',LANQIAO)
    evidence=raw_suggestions('lanqiao',{'fields':LANQIAO})['data']
    evidence['competition_level']='省级'
    response=env[1].post(f'/api/ocr/jobs/{job_id}/confirm-material',json={'year':2026,'data':evidence,'manual_only':True})
    assert response.status_code==201,response.json
    assert response.json['material']['category']=='competition_evidence'
    assert response.json['material']['data']['competition_level']=='省级'
    assert response.json['material']['competition_rule_package_id'] is None
    assert ScoreEntry.query.count()==Application.query.count()==0


def test_teacher_cannot_read_unsubmitted_ocr_by_guessing_job_url(env):
    from test_ocr_material_fields import prepared_job
    job_id,_=prepared_job(env)
    owner=db.session.get(User,env[2]['student'])
    teacher=User(username='teacher_draft',password='x',name='教师',role='teacher',status='active',faculty_id=owner.faculty_id)
    db.session.add(teacher);db.session.commit();login(env[1],teacher.id)
    assert env[1].get(f'/api/ocr/jobs/{job_id}').status_code==403


def test_attachment_recognition_alias_reuses_same_bound_queue(env):
    row,path,job=queued_material(env)
    response=env[1].post(path+'/recognize',json={'version':row['version'],'attachment_id':row['attachments'][0]['id'],'project_key':'computer-design'})
    assert response.status_code==202,response.json
    assert response.json['id']==job['job_id']
    assert OCRJob.query.count()==CompetitionOcrJob.query.count()==1


def test_recognition_alias_rejects_wrong_adapter_even_with_active_task(env):
    row,path,job=queued_material(env)
    response=env[1].post(path+'/recognize',json={'version':row['version'],'attachment_id':row['attachments'][0]['id'],'project_key':'lanqiao'})
    assert response.status_code==400,response.json
    assert OCRJob.query.count()==1


def test_changed_material_can_start_new_version_without_reusing_old_job(env):
    row,path,old=queued_material(env)
    edited=env[1].patch(path,json={'version':row['version'],'data':facts()|{'project_name':'新版本作品'}})
    assert edited.status_code==200,edited.json
    newer=env[1].post(path+'/ocr',json={'version':edited.json['version']})
    assert newer.status_code==201,newer.json
    assert newer.json['job_id']!=old['job_id']
    assert run_one_ocr(env[0],Provider())
    assert env[1].get(path+'/ocr/'+old['job_id']).json['status']=='ignored'
    assert run_one_ocr(env[0],Provider())
    assert env[1].get(path+'/ocr/'+newer.json['job_id']).json['status']=='completed'


def test_submit_rechecks_original_after_ocr_completion(env):
    row,path,job=queued_material(env)
    assert run_one_ocr(env[0],Provider())
    from services.materials.service import stored_path
    original=db.session.get(MaterialRecord,row['id']).attachments[0]
    stored_path(original.stored_name).write_bytes(b'tampered after OCR')
    response=env[1].post(path+'/submit',json={'version':row['version']})
    assert response.status_code==409 and response.json['code']=='original_integrity_failed'
    assert db.session.get(MaterialRecord,row['id']).status=='draft'
    assert ScoreEntry.query.count()==0


def test_manual_appointment_can_be_submitted_and_reviewed_without_ocr(env):
    from test_material_interfaces import SAMPLES
    login(env[1],env[2]['student'])
    response=env[1].post('/api/materials/student_work/records',json={'year':2026,'data':SAMPLES['student_work'],'manual_only':True})
    assert response.status_code==201,response.json
    row=response.json;assert row['manual_only']
    path=f"/api/materials/student_work/records/{row['id']}"
    edited=env[1].patch(path,json={'version':row['version'],'data':row['data']})
    assert edited.status_code==200 and edited.json['manual_only']
    submitted=env[1].post(path+'/submit',json={'version':edited.json['version']})
    assert submitted.status_code==200,submitted.json
    owner=db.session.get(User,env[2]['student']);teacher=User(username='manual_teacher',password='x',name='教师',role='teacher',status='active',faculty_id=owner.faculty_id)
    db.session.add(teacher);db.session.commit();login(env[1],teacher.id)
    assert len(env[1].get('/api/materials/student_work/records').json['records'])==1
    reviewed=env[1].post(path+'/review',json={'version':submitted.json['version'],'decision':'verified','comment':'已核对学校任职记录'})
    assert reviewed.status_code==200,reviewed.json
    assert OCRJob.query.count()==ScoreEntry.query.count()==0


def test_manual_fields_and_originals_are_created_atomically(env):
    login(env[1],env[2]['student'])
    payload={'year':'2026','data':json.dumps({'document_type':'research_report','report_no':'R-1','database':'WoS'}),'files':(io.BytesIO(b'original proof'),'proof.pdf')}
    response=env[1].post('/api/materials/research/records',data=payload)
    assert response.status_code==201,response.json
    assert response.json['manual_only'] and len(response.json['attachments'])==1
    assert OCRJob.query.count()==0


def test_invalid_manual_original_creates_no_partial_draft(env):
    login(env[1],env[2]['student'])
    payload={'year':'2026','data':json.dumps({'document_type':'research_report','report_no':'R-1','database':'WoS'}),'files':(io.BytesIO(b'bad'),'proof.exe')}
    response=env[1].post('/api/materials/research/records',data=payload)
    assert response.status_code==400
    assert MaterialRecord.query.count()==0
