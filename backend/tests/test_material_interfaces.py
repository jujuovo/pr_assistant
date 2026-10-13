"""五类非OCR接口、校方数据对照、权限、并发及不触发自动计分的回归。"""
import copy
import io
import json
from pathlib import Path
import pytest
from extensions import db
from models import Student, Application, User
from material_models import MaterialRecord, MaterialSource, MaterialAttachment
from automation_models import AutomationBatch
from certificate_models import CertificateAssessment
from conftest import login


SAMPLES={
    'academic':{'term':'2025-2026-2','courses':[
        {'course_code':'A','course_name':'数据结构','credits':2,'score':80,'full_score':100},
        {'course_code':'B','course_name':'数学','credits':3,'score':90,'full_score':100}]},
    'competition':{'competition_name':'蓝桥杯','organizer':'比赛主办单位','competition_level':'省级',
                   'award_level':'二等奖','award_date':'2026-05-08','certificate_no':'1234567890','project_key':'lanqiao'},
    'language':{'exam_name':'CET6','language':'英语','score':560,'full_score':710,
                'test_date':'2025-12-20','certificate_no':'CET-2025-001'},
    'student_work':{'as_of':'2026-01-31','appointments':[
        {'organization':'学生会','position':'部长','position_level':'院级','start_date':'2026-01-01',
         'end_date':'2026-01-10','assessment_result':'优秀'},
        {'organization':'班级','position':'班长','position_level':'班级','start_date':'2026-01-05',
         'end_date':'2026-01-20','assessment_result':'合格'}]},
    'honor':{'honor_name':'优秀学生干部','honor_level':'校级','issuer':'学校',
             'award_date':'2026-06-01','certificate_no':'HONOR-001'},
}


def create(env,category='honor',data=None,**extra):
    login(env[1],env[2]['student'])
    response=env[1].post(f'/api/materials/{category}/records',json={'year':2026,'data':data or copy.deepcopy(SAMPLES[category]),**extra})
    assert response.status_code==201,response.json
    return response.json


def endpoint(row,action=''):
    return f"/api/materials/{row['category']}/records/{row['id']}"+('/'+action if action else '')


@pytest.mark.parametrize('category',list(SAMPLES))
def test_five_types_are_persisted_but_never_ocr_or_bonus(env,category,monkeypatch):
    from services.recognition.provider import PaddleProvider
    monkeypatch.setattr(PaddleProvider,'__init__',lambda *a,**k:pytest.fail('不得加载OCR模型'))
    row=create(env,category)
    assert row['status']=='draft' and row['bonus_result'] is None
    assert row['analysis']['ocr_executed'] is False
    assert row['analysis']['bonus_calculation']=='not_implemented'
    assert env[1].get(endpoint(row)).json['data']==row['data']
    assert len(env[1].get(f'/api/materials/{category}/records').json['records'])==1
    unsupported=env[1].post(endpoint(row,'recognize'))
    assert unsupported.status_code==501 and unsupported.json['code']=='recognition_not_implemented'
    assert AutomationBatch.query.count()==0 and CertificateAssessment.query.count()==0
    student=Student.query.filter_by(student_id='S1').one()
    assert student.academic_score==80 and student.cet6_score is None


def test_academic_csv_weighting_and_numeric_normalization(env):
    login(env[1],env[2]['student'])
    csv='course_code,course_name,credits,score,full_score\nA,数据结构,2.0,80.0,100\nB,数学,3,90,100\n'
    response=env[1].post('/api/materials/academic/parse-csv',data={
        'term':'2025-2026-2','file':(io.BytesIO(csv.encode('utf-8-sig')),'grades.csv')})
    assert response.status_code==200,response.json
    assert response.json['analysis']['weighted_average_100']=='86.0000'
    assert response.json['analysis']['total_credits']=='5'
    assert response.json['persisted'] is False and MaterialRecord.query.count()==0
    assert response.json['data']['courses'][0]['credits']=='2'
    row=create(env,'academic',response.json['data'])
    assert row['analysis']['weighted_average_100']=='86.0000'


def test_student_work_inclusive_days_and_overlap(env):
    row=create(env,'student_work')
    assert [x['tenure_days'] for x in row['analysis']['appointments']]==[10,16]
    assert row['analysis']['unique_tenure_days']==20 and row['analysis']['warnings']
    data=copy.deepcopy(SAMPLES['student_work'])
    data['appointments'][1]['end_date']=None
    result=env[1].patch(endpoint(row),json={'version':row['version'],'data':data})
    assert result.status_code==200
    assert result.json['analysis']['unique_tenure_days']==31


@pytest.mark.parametrize('changes',[
    {'score':'NaN'},{'score':'Infinity'},{'score':True},{'score':-1},{'score':711},{'full_score':0},
    {'test_date':'2026-02-30'},{'bonus_score':4}])
def test_invalid_language_data_is_not_saved(env,changes):
    login(env[1],env[2]['student'])
    data=copy.deepcopy(SAMPLES['language']); data.update(changes)
    response=env[1].post('/api/materials/language/records',json={'year':2026,'data':data})
    assert response.status_code==400 and MaterialRecord.query.count()==0


def test_course_duplicates_and_invalid_tenure_are_rejected(env):
    login(env[1],env[2]['student'])
    academic=copy.deepcopy(SAMPLES['academic']); academic['courses'][1]['course_code']='A'
    assert env[1].post('/api/materials/academic/records',json={'year':2026,'data':academic}).status_code==400
    work=copy.deepcopy(SAMPLES['student_work']); work['appointments'][0]['end_date']='2025-12-31'
    assert env[1].post('/api/materials/student_work/records',json={'year':2026,'data':work}).status_code==400


def source_payload(category='honor',revision=1,data=None,external_id='REF-001'):
    return {'source_name':'学校平台导出名册','source_url':'https://school.example.edu/records',
            'records':[{'student_id':'S1','category':category,'year':2026,'external_id':external_id,
                        'revision':revision,'data':data or copy.deepcopy(SAMPLES[category])}]}


@pytest.mark.parametrize('category',list(SAMPLES))
def test_official_snapshot_matching_does_not_confirm_authenticity(env,category):
    data=copy.deepcopy(SAMPLES[category]); data['reference_id']='REF-001'
    row=create(env,category,data)
    login(env[1],env[2]['admin'])
    source=env[1].post('/api/materials/sources/import',json=source_payload(category))
    assert source.status_code==201,source.json
    assert env[1].get(f"/api/materials/sources/{source.json['created_ids'][0]}").status_code==200
    login(env[1],env[2]['student'])
    checked=env[1].post(endpoint(row,'check'),json={'version':row['version']})
    assert checked.status_code==200,checked.json
    assert checked.json['check_report']['status']=='consistent'
    assert checked.json['check_report']['authenticity']=='not_assessed'
    assert checked.json['status']=='draft' and checked.json['bonus_result'] is None


def test_sources_are_revisioned_idempotent_and_import_is_atomic(env):
    login(env[1],env[2]['admin'])
    payload=source_payload()
    first=env[1].post('/api/materials/sources/import',json=payload)
    assert first.status_code==201
    repeated=env[1].post('/api/materials/sources/import',json=payload)
    assert repeated.status_code==200 and repeated.json['unchanged_count']==1
    edited=copy.deepcopy(payload); edited['records'][0]['data']['honor_level']='院级'
    assert env[1].post('/api/materials/sources/import',json=edited).status_code==409
    assert MaterialSource.query.count()==1
    edited['records'][0]['revision']=2
    assert env[1].post('/api/materials/sources/import',json=edited).status_code==201
    assert MaterialSource.query.count()==2
    invalid=source_payload(external_id='NEW'); second=copy.deepcopy(invalid['records'][0]); second['student_id']='UNKNOWN'
    invalid['records'].append(second)
    assert env[1].post('/api/materials/sources/import',json=invalid).status_code==403
    assert MaterialSource.query.count()==2


def test_source_mismatch_and_missing_are_manual_evidence(env):
    data=copy.deepcopy(SAMPLES['honor']); data['reference_id']='REF-001'
    row=create(env,data=data)
    missing=env[1].post(endpoint(row,'check'),json={'version':row['version']})
    assert missing.json['check_report']['status']=='awaiting_official_data'
    login(env[1],env[2]['admin'])
    payload=source_payload(); payload['records'][0]['data']['honor_level']='院级'
    assert env[1].post('/api/materials/sources/import',json=payload).status_code==201
    login(env[1],env[2]['student'])
    mismatch=env[1].post(endpoint(row,'check'),json={'version':missing.json['version']})
    assert mismatch.json['check_report']['status']=='mismatch'
    assert mismatch.json['check_report']['differences'][0]['field']=='honor_level'
    assert mismatch.json['status']=='draft'


def test_manual_review_lifecycle_permissions_and_versions(env):
    row=create(env)
    assert env[1].post(endpoint(row,'review'),json={'version':1,'decision':'verified','comment':'测试'}).status_code==403
    submitted=env[1].post(endpoint(row,'submit'),json={'version':1})
    assert submitted.json['status']=='submitted'
    login(env[1],env[2]['other'])
    assert env[1].get(endpoint(row)).status_code==403
    assert env[1].get('/api/materials/honor/records').json['records']==[]
    login(env[1],env[2]['admin'])
    assert env[1].post(endpoint(row,'review'),json={'version':1,'decision':'verified','comment':'核验'}).status_code==409
    correction=env[1].post(endpoint(row,'review'),json={'version':2,'decision':'needs_correction','comment':'请补充颁发单位证明'})
    assert correction.status_code==200
    login(env[1],env[2]['student'])
    corrected=env[1].patch(endpoint(row),json={'version':3,'data':SAMPLES['honor']})
    assert corrected.json['status']=='draft'
    assert env[1].post(endpoint(row,'submit'),json={'version':4}).status_code==200
    login(env[1],env[2]['admin'])
    verified=env[1].post(endpoint(row,'review'),json={'version':5,'decision':'verified','comment':'已核对校方名册'})
    assert verified.json['status']=='verified' and verified.json['bonus_result'] is None
    events=env[1].get(endpoint(row,'events')).json['events']
    assert [e['action'] for e in events]==['created','submitted','reviewed','edited','submitted','reviewed']
    login(env[1],env[2]['student'])
    assert env[1].patch(endpoint(row),json={'version':6,'data':SAMPLES['honor']}).status_code==409
    assert env[1].post(endpoint(row,'withdraw'),json={'version':6}).status_code==409
    assert Student.query.filter_by(student_id='S1').one().academic_score==80


def test_attachment_authentication_and_stale_upload_rollback(env):
    row=create(env)
    uploaded=env[1].post(endpoint(row,'attachments'),data={'version':'1','files':(io.BytesIO(b'proof bytes'),'../证明.pdf')})
    assert uploaded.status_code==201,uploaded.json
    attachment=uploaded.json['attachments'][0]
    assert attachment['filename']=='证明.pdf' and attachment['size']==11
    assert env[1].get(attachment['url']).data==b'proof bytes'
    login(env[1],env[2]['other'])
    assert env[1].get(attachment['url']).status_code==403
    login(env[1],env[2]['student'])
    stale=env[1].post(endpoint(row,'attachments'),data={'version':'1','files':(io.BytesIO(b'new'),'new.pdf')})
    assert stale.status_code==409 and MaterialAttachment.query.count()==1
    invalid=env[1].post(endpoint(row,'attachments'),data={'version':'2','files':(io.BytesIO(b'exe'),'malware.exe')})
    assert invalid.status_code==400 and MaterialAttachment.query.count()==1
    assert len(list(Path(env[0].config['MATERIAL_STORAGE_FOLDER']).iterdir()))==1


def test_application_link_does_not_mutate_or_delete_scores(env):
    student=Student.query.filter_by(student_id='S1').one()
    application=Application(student_id='S1',student_name='张三',faculty_id=student.faculty_id,
                            department_id=student.department_id,major_id=student.major_id,
                            application_type='academic',project_name='材料测试',status='pending',self_score=3)
    db.session.add(application); db.session.commit()
    row=create(env,application_id=application.id)
    assert row['application_id']==application.id
    assert env[1].post(endpoint(row,'submit'),json={'version':1}).status_code==200
    login(env[1],env[2]['admin'])
    assert env[1].post(endpoint(row,'review'),json={'version':2,'decision':'verified','comment':'人工核验'}).status_code==200
    db.session.refresh(application)
    assert application.self_score==3 and application.final_score is None and application.status=='pending'
    assert env[1].delete(f'/api/applications/{application.id}').status_code==409


def test_auth_schema_student_import_and_input_score_forbidden(env):
    assert env[1].get('/api/materials/types').status_code==401
    login(env[1],env[2]['student'])
    types=env[1].get('/api/materials/types')
    assert types.status_code==200 and len(types.json['types'])==5
    assert all(not t['auto_bonus_enabled'] for t in types.json['types'])
    assert env[1].post('/api/materials/sources/import',json=source_payload()).status_code==403
    assert env[1].post('/api/materials/honor/records',json={'year':2026,'data':SAMPLES['honor'],'final_score':6}).status_code==400
    assert env[1].post('/api/materials/honor/records',json=[]).status_code==400
    assert env[1].get('/api/materials/unknown/records').status_code==404


def test_material_migration_matches_models_and_reverses(env):
    import importlib.util
    from sqlalchemy import inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from material_models import MaterialEvent
    tables=[MaterialAttachment.__table__,MaterialEvent.__table__,MaterialSource.__table__,MaterialRecord.__table__]
    path=Path(__file__).parents[1]/'migrations/versions/20261013_material_interfaces.py'
    spec=importlib.util.spec_from_file_location('material_migration',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    with db.engine.begin() as connection:
        for table in tables: table.drop(connection)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            for table in tables:
                assert {c['name'] for c in inspect(connection).get_columns(table.name)}=={c.name for c in table.columns}
            module.downgrade()
            assert not inspect(connection).has_table('material_record')
            module.upgrade()


def test_openapi_matches_registered_routes_and_all_references(env):
    app,client,users=env
    login(client,users['student'])
    response=client.get('/api/materials/openapi.json')
    assert response.status_code==200
    spec=response.json
    assert spec['openapi']=='3.0.3'
    import re
    registered={re.sub(r'<(?:int:)?(\w+)>',r'{\1}',rule.rule):set(rule.methods)-{'OPTIONS','HEAD'}
                for rule in app.url_map.iter_rules() if rule.endpoint.startswith('materials.')}
    assert set(registered)==set(spec['paths'])
    for path,methods in registered.items():
        assert {key.upper() for key in spec['paths'][path] if key in ('get','post','patch')}==methods
    def visit(value):
        if isinstance(value,dict):
            if '$ref' in value:
                parts=value['$ref'].removeprefix('#/').split('/')
                target=spec
                for part in parts: target=target[part]
            for child in value.values(): visit(child)
        elif isinstance(value,list):
            for child in value: visit(child)
    visit(spec)
    examples=spec['paths']['/api/materials/{category}/records']['post']['requestBody']['content']['application/json']['examples']
    assert set(examples)==set(SAMPLES)


def test_withdraw_unverified_preserves_audit(env):
    row=create(env)
    submitted=env[1].post(endpoint(row,'submit'),json={'version':1}).json
    withdrawn=env[1].post(endpoint(row,'withdraw'),json={'version':submitted['version']})
    assert withdrawn.status_code==200 and withdrawn.json['status']=='draft'
    assert env[1].get(endpoint(row,'events')).json['events'][-1]['action']=='withdrawn'
