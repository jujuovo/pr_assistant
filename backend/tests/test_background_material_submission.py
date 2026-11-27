from conftest import prepare_final_stage
"""Single-upload/background workflow against real Flask routes and the leased worker."""
import copy
import io
import json
from pathlib import Path
from unittest.mock import patch
from conftest import login
from extensions import db
from material_models import MaterialRecord, MaterialAttachment, CompetitionOcrJob
from ocr_models import OCRJob
from workflow_models import ScoreEntry
from models import User
from test_ocr_workflow_integration import setup_formal, facts, picture, Provider
from services.competition_ocr.worker import run_one_ocr


def upload(env, data=None, name="proof.png", payload=None):
    setup_formal(env);login(env[1],env[2]["student"])
    return env[1].post('/api/materials/competition/records',data={
        'year':'2028','data':json.dumps(data or facts()),
        'files':(io.BytesIO(picture() if payload is None else payload),name)})


def test_single_upload_persists_queue_can_leave_submit_another_then_refresh(env):
    first=upload(env);assert first.status_code==201,first.json
    second=upload(env,facts()|{'project_name':'第二个作品'});assert second.status_code==201,second.json
    assert MaterialRecord.query.count()==2 and MaterialAttachment.query.count()==2
    assert OCRJob.query.count()==CompetitionOcrJob.query.count()==2
    assert first.json['workflow_state']=='ocr_queued'
    assert first.json['recognition_status']=='queued'
    assert first.json['data']['project_name']=='测试作品'
    assert run_one_ocr(env[0],Provider()) and run_one_ocr(env[0],Provider())
    # Login session/page changes never own or cancel the jobs.
    login(env[1],env[2]['student'])
    rows=env[1].get('/api/materials/competition/records').json['records']
    assert [r['workflow_state'] for r in rows]==['ready_to_submit']*2
    assert [r['data']['project_name'] for r in rows]==['测试作品','第二个作品']
    assert rows[0]['ocr_assessment']['declared_estimate']==facts_score(rows[0])
    assert ScoreEntry.query.count()==0


def facts_score(row):
    return row['data']['candidate_score']


def test_readonly_estimate_validates_but_writes_nothing(env):
    setup_formal(env);login(env[1],env[2]['student'])
    result=env[1].post('/api/materials/competition/estimate',json={'data':facts()})
    assert result.status_code==200,result.json
    assert result.json['requires_teacher_review'] is True
    assert MaterialRecord.query.count()==ScoreEntry.query.count()==0
    invalid=env[1].post('/api/materials/competition/estimate',json={'data':facts()|{'candidate_score':999}})
    assert invalid.status_code==400
    login(env[1],env[2]['other'])
    assert env[1].post('/api/materials/competition/estimate',json={'data':facts()}).status_code==403


def test_pdf_single_upload_is_ready_for_manual_review_without_ocr(env):
    response=upload(env,name='proof.pdf',payload=b'%PDF test original')
    assert response.status_code==201,response.json
    assert response.json['workflow_state']=='ready_to_submit'
    assert response.json['ocr_assessment']['job'] is None
    assert OCRJob.query.count()==0


def test_unsupported_formal_event_does_not_create_useless_queue(env):
    data=facts()|{'competition_id':'c01-international-internet-innovation'}
    # Pick an actual official event with no adapter rather than manufacture a catalog entry.
    setup_formal(env)
    from workflow_models import CompetitionRulePackage
    p=CompetitionRulePackage.query.filter_by(status='current').one()
    item=next(i for i in p.snapshot['catalog'] if i['event_family'] not in {'lanqiao-cup','computer-design','challenge-cup-business-plan','csp'} and 'national' in i['levels'] and i['event_family'] not in {'icpc','ccpc'})
    data['competition_id']=item['competition_id']
    response=upload(env,data)
    assert response.status_code==201,response.json
    assert response.json['workflow_state']=='ready_to_submit'
    assert OCRJob.query.count()==0


def test_bad_image_rolls_back_draft_attachment_job_and_private_inputs(env):
    response=upload(env,payload=b'not an image')
    assert response.status_code==400,response.json
    assert MaterialRecord.query.count()==MaterialAttachment.query.count()==OCRJob.query.count()==0
    assert not list(Path(env[0].config['MATERIAL_STORAGE_FOLDER']).glob('*'))
    assert not list(Path(env[0].config['OCR_STORAGE_FOLDER']).glob('*'))


def test_commit_failure_cleans_input_and_material_files(env):
    setup_formal(env)
    with patch.object(db.session,'commit',side_effect=RuntimeError('forced failure')):
        with __import__('pytest').raises(RuntimeError): upload_without_setup(env)
    assert MaterialRecord.query.count()==OCRJob.query.count()==0
    assert not list(Path(env[0].config['MATERIAL_STORAGE_FOLDER']).glob('*'))
    assert not list(Path(env[0].config['OCR_STORAGE_FOLDER']).glob('*'))


def upload_without_setup(env):
    login(env[1],env[2]['student'])
    return env[1].post('/api/materials/competition/records',data={'year':'2028','data':json.dumps(facts()),'files':(io.BytesIO(picture()),'proof.png')})


def test_edit_and_optional_replacement_is_atomic_and_old_job_stays_stale(env):
    response=upload(env);row=response.json
    path=f"/api/materials/competition/records/{row['id']}"
    changed=env[1].patch(path,data={'version':str(row['version']),'data':json.dumps(facts()|{'project_name':'手工修改'}),'files':(io.BytesIO(picture()),'revised.png')})
    assert changed.status_code==200,changed.json
    assert len(changed.json['attachments'])==2
    assert run_one_ocr(env[0],Provider())
    assert CompetitionOcrJob.query.order_by(CompetitionOcrJob.id).first().status=='ignored'
    assert run_one_ocr(env[0],Provider())
    latest=env[1].get(path).json
    assert latest['data']['project_name']=='手工修改'
    assert latest['workflow_state']=='ready_to_submit'
    assert len(latest['ocr_assessment']['differences'])>=1


def test_queue_processing_and_failure_states_persist_across_requests(env):
    result=upload(env).json
    job=db.session.get(OCRJob,result['ocr_assessment']['job']['job_id'])
    job.status='processing';db.session.commit()
    path=f"/api/materials/competition/records/{result['id']}"
    assert env[1].get(path).json['workflow_state']=='ocr_running'
    from use_cases.competition_ocr import fail_competition_ocr
    fail_competition_ocr(job.id,'模型不可用');db.session.commit()
    assert env[1].get(path).json['workflow_state']=='ocr_failed'


def test_ocr_conditional_score_and_difference_never_change_declared_score(env):
    result=upload(env).json
    assert run_one_ocr(env[0],Provider())
    row=env[1].get(f"/api/materials/competition/records/{result['id']}").json
    advice=row['ocr_assessment']
    assert advice['ocr_suggested_score'] is not None
    assert 'level' in advice['missing_fields']
    assert advice['review_mode']=='manual_confirmation'
    assert row['data']==result['data'] and ScoreEntry.query.count()==0
    # Maturity is not inferred from a score or a successful OCR pass.
    assert advice['mature_adapter'] is False and advice['requires_teacher_review'] is True


def test_cross_faculty_cannot_read_queue_state_or_assessment(env):
    row=upload(env).json;login(env[1],env[2]['other'])
    assert env[1].get(f"/api/materials/competition/records/{row['id']}").status_code==403
    assert env[1].get('/api/ocr/jobs/'+row['ocr_assessment']['job']['job_id']).status_code==403


def test_teacher_must_acknowledge_ocr_uncertainty_and_audit_is_preserved(env):
    row=upload(env).json
    assert run_one_ocr(env[0],Provider())
    path=f"/api/materials/competition/records/{row['id']}"
    submitted=env[1].post(path+'/submit',json={'version':row['version']}).json
    teacher=User(username='reviewer',password='test',name='教师',role='teacher',status='active',faculty_id=row['faculty_id'])
    db.session.add(teacher);db.session.commit()
    prepare_final_stage()
    login(env[1],teacher.id)
    command={'version':submitted['version'],'decision':'approve','comment':'','idempotency_key':'new-ocr-review'}
    denied=env[1].post(path+'/review',json=command)
    assert denied.status_code==409 and denied.json['code']=='ocr_manual_confirmation_required'
    assert ScoreEntry.query.count()==0
    result=env[1].post(path+'/review',json=command|{'ocr_confirmed':True})
    assert result.status_code==200,result.json
    assert ScoreEntry.query.count()==1
    explained=env[1].get('/api/workflow/students/S1/score/current')
    assert explained.status_code==200,explained.json
    item=explained.json['entries'][0]
    assert item['project_source']['name']=='测试作品'
    assert item['scoring_status']=='scored'
    assert item['rule_label']=='学业竞赛计分规则（第1版）'
    assert explained.json['rule_versions'][0]['label']==item['rule_label']
    assert explained.json['rule_version_ids'][0]<0  # Internal identity unchanged, no version guess on client.
    from material_models import MaterialEvent
    details=MaterialEvent.query.filter_by(record_id=row['id'],action='competition_approved').one().details
    assert details['ocr_confirmed'] is True
    assert details['comment']==''
    assert details['ocr_assessment_snapshot']['review_mode']=='manual_confirmation'
    assert details['ocr_raw_snapshot']['report']['category']=='computer-design'
    replay=env[1].post(path+'/review',json=command|{'ocr_confirmed':True})
    assert replay.status_code==200 and replay.json['replayed'] is True
    assert env[1].get(path+'/review-context').json['ocr_assessment']['requires_teacher_review'] is True


def test_editing_ocr_material_cannot_disable_original_integrity(env):
    row=upload(env).json
    assert run_one_ocr(env[0],Provider())
    path=f"/api/materials/competition/records/{row['id']}"
    edited=env[1].patch(path,json={'version':row['version'],'data':facts()|{'project_name':'已修改'}}).json
    assert edited['ocr_raw_terms'] is None
    from services.materials.service import stored_path
    item=MaterialAttachment.query.filter_by(record_id=row['id']).one()
    stored_path(item.stored_name).write_bytes(b'changed')
    result=env[1].post(path+'/submit',json={'version':edited['version']})
    assert result.status_code==409 and result.json['code']=='original_integrity_failed'


def test_manual_approval_without_comment_but_rejections_need_reason(env):
    setup_formal(env);login(env[1],env[2]['student'])
    created=env[1].post('/api/materials/social_practice/records',json={'year':2028,'data':{'document_type':'practice_proof','team':'测试队','period_as_printed':'2026年暑期'}})
    assert created.status_code==201,created.json
    row=created.json;path=f"/api/materials/social_practice/records/{row['id']}"
    submitted=env[1].post(path+'/submit',json={'version':row['version']}).json
    teacher=User(username='manual_reviewer',password='test',name='教师',role='teacher',status='active',faculty_id=row['faculty_id'])
    db.session.add(teacher);db.session.commit()
    prepare_final_stage()
    login(env[1],teacher.id)
    for decision in ['needs_correction','rejected']:
        denied=env[1].post(path+'/review',json={'version':submitted['version'],'decision':decision,'comment':' '})
        assert denied.status_code==400,denied.json
    approved=env[1].post(path+'/review',json={'version':submitted['version'],'decision':'verified'})
    assert approved.status_code==200,approved.json
    assert approved.json['status']=='verified' and ScoreEntry.query.count()==0
    from material_models import MaterialEvent
    assert MaterialEvent.query.filter_by(record_id=row['id'],action='reviewed').one().details['comment']==''
