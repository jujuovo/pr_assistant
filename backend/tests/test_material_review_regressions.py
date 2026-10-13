"""复查发现的越权、异常输入和核验误报回归。"""
import copy
import csv
import io
from pathlib import Path

import pytest
from extensions import db
from models import Application, Student
from material_models import MaterialAttachment, MaterialRecord, MaterialSource
from conftest import login
from test_material_interfaces import create, endpoint, SAMPLES, source_payload


def linked(env):
    student=Student.query.filter_by(student_id='S1').one()
    application=Application(student_id='S1',student_name=student.student_name,faculty_id=student.faculty_id,
        department_id=student.department_id,major_id=student.major_id,application_type='academic',
        project_name='关联申请',status='pending',self_score=2)
    db.session.add(application); db.session.commit()
    create(env,application_id=application.id)
    return application


def test_linked_application_cannot_change_owner(env):
    application=linked(env)
    owner=Student.query.filter_by(student_id='S1').one()
    other=Student(student_id='S2',student_name='李四',faculty_id=owner.faculty_id,
                  department_id=owner.department_id,major_id=owner.major_id)
    db.session.add(other); db.session.commit()
    response=env[1].put(f'/api/applications/{application.id}',json={'studentId':'S2'})
    assert response.status_code==400
    db.session.refresh(application)
    assert application.student_id=='S1'


def test_linked_application_student_cannot_approve_or_change_score(env):
    application=linked(env)
    response=env[1].post(f'/api/applications/{application.id}/review',json={
        'status':'approved','finalScore':5,'reviewedBy':'学生自己'})
    assert response.status_code==403
    assert env[1].put(f'/api/applications/{application.id}',json={'finalScore':8}).status_code==400
    db.session.refresh(application)
    assert application.status=='pending' and application.final_score is None


def test_linked_application_rejects_other_faculty_and_preserves_manual_teacher_review(env):
    application=linked(env)
    login(env[1],env[2]['other'])
    assert env[1].get(f'/api/applications/{application.id}').status_code==403
    assert env[1].post(f'/api/applications/{application.id}/review',json={'status':'approved','finalScore':2}).status_code==403
    login(env[1],env[2]['admin'])
    assert env[1].post(f'/api/applications/{application.id}/review',json={
        'status':'approved','finalScore':1.25,'reviewedBy':'管理员'}).status_code==200


def test_large_csv_header_is_a_validation_error(env):
    login(env[1],env[2]['student'])
    content='x'*(csv.field_size_limit()+1)+',course_name,credits,score,full_score\n'
    response=env[1].post('/api/materials/academic/parse-csv',data={
        'term':'2026','file':(io.BytesIO(content.encode()),'grades.csv')})
    assert response.status_code==400


def test_week_date_is_not_a_calendar_date_contract(env):
    login(env[1],env[2]['student'])
    data=copy.deepcopy(SAMPLES['honor']); data['award_date']='2026-W01-1'
    assert env[1].post('/api/materials/honor/records',json={'year':2026,'data':data}).status_code==400


@pytest.mark.parametrize('bad_text',['坏\x00字段','坏\ud800字段'])
def test_text_unusable_by_database_is_rejected(env,bad_text):
    login(env[1],env[2]['student'])
    data=copy.deepcopy(SAMPLES['honor']); data['honor_name']=bad_text
    assert env[1].post('/api/materials/honor/records',json={'year':2026,'data':data}).status_code==400


def test_processing_route_is_not_an_official_certificate_field(env):
    data=copy.deepcopy(SAMPLES['competition']); data['reference_id']='REF-001'
    row=create(env,'competition',data)
    source=copy.deepcopy(SAMPLES['competition']); source.pop('project_key')
    login(env[1],env[2]['admin'])
    assert env[1].post('/api/materials/sources/import',json=source_payload('competition',data=source)).status_code==201
    login(env[1],env[2]['student'])
    checked=env[1].post(endpoint(row,'check'),json={'version':1})
    assert checked.status_code==200
    assert checked.json['check_report']['status']=='consistent'


def test_optional_blank_certificate_no_is_not_a_mismatch(env):
    data=copy.deepcopy(SAMPLES['honor']); data.pop('certificate_no'); data['reference_id']='REF-001'
    row=create(env,'honor',data)
    source=copy.deepcopy(data); source.pop('reference_id'); source['certificate_no']=''
    login(env[1],env[2]['admin'])
    assert env[1].post('/api/materials/sources/import',json=source_payload('honor',data=source)).status_code==201
    login(env[1],env[2]['student'])
    assert env[1].post(endpoint(row,'check'),json={'version':1}).json['check_report']['status']=='consistent'


def test_download_rejects_changed_original(env):
    row=create(env)
    uploaded=env[1].post(endpoint(row,'attachments'),data={'version':'1','files':(io.BytesIO(b'original'),'file.pdf')})
    assert uploaded.status_code==201
    attachment=db.session.get(MaterialAttachment,uploaded.json['attachments'][0]['id'])
    path=Path(env[0].config['MATERIAL_STORAGE_FOLDER'])/attachment.stored_name
    path.write_bytes(b'modified')
    assert env[1].get(uploaded.json['attachments'][0]['url']).status_code==409


def test_review_retains_attachment_snapshot(env):
    row=create(env)
    uploaded=env[1].post(endpoint(row,'attachments'),data={'version':'1','files':(io.BytesIO(b'original'),'file.pdf')}).json
    submitted=env[1].post(endpoint(row,'submit'),json={'version':uploaded['version']}).json
    login(env[1],env[2]['admin'])
    reviewed=env[1].post(endpoint(row,'review'),json={'version':submitted['version'],
                      'decision':'needs_correction','comment':'补充材料'})
    assert reviewed.status_code==200
    details=env[1].get(endpoint(row,'events')).json['events'][-1]['details']
    assert details['attachments_snapshot']==[{
        k:uploaded['attachments'][0][k] for k in ('id','filename','size','sha256')}]


def test_control_characters_in_download_name_are_rejected(env):
    row=create(env)
    response=env[1].post(endpoint(row,'attachments'),data={'version':'1',
        'files':(io.BytesIO(b'original'),'bad\x00name.pdf')})
    assert response.status_code==400


@pytest.mark.parametrize('url',['/api/applications','/api/applications/pending'])
def test_linked_application_lists_cannot_leak_to_other_faculty_or_anonymous(env,url):
    application=linked(env)
    login(env[1],env[2]['other'])
    response=env[1].get(url)
    assert response.status_code==200
    assert application.id not in [row['id'] for row in response.json]
    with env[1].session_transaction() as state: state.clear()
    assert application.id not in [row['id'] for row in env[1].get(url).json]
    login(env[1],env[2]['student'])
    assert application.id in [row['id'] for row in env[1].get(url).json]


def test_legacy_optional_fields_are_compared_without_rewriting_snapshots(env):
    data=copy.deepcopy(SAMPLES['honor']); data['reference_id']='REF-001'
    row=create(env,data=data)
    login(env[1],env[2]['admin'])
    env[1].post('/api/materials/sources/import',json=source_payload())
    record=db.session.get(MaterialRecord,row['id'])
    source=MaterialSource.query.one()
    # 模拟上个版本留下的“省略可选字段”快照。
    older=dict(source.data); older.pop('certificate_no'); source.data=older
    declared=dict(record.data); declared['certificate_no']=''; record.data=declared
    db.session.commit()
    digest=source.digest
    login(env[1],env[2]['student'])
    checked=env[1].post(endpoint(row,'check'),json={'version':row['version']})
    assert checked.json['check_report']['status']=='consistent'
    db.session.refresh(source)
    assert 'certificate_no' not in source.data and source.digest==digest


def test_partial_file_write_rolls_back_and_removes_only_new_file(env,monkeypatch):
    row=create(env)
    root=Path(env[0].config['MATERIAL_STORAGE_FOLDER'])
    original_open=Path.open
    class BrokenWriter:
        def __init__(self,stream): self.stream=stream
        def __enter__(self): return self
        def __exit__(self,*args): self.stream.close()
        def write(self,payload):
            self.stream.write(payload[:2])
            raise OSError('simulated full disk')
    def failing_open(path,*args,**kwargs):
        stream=original_open(path,*args,**kwargs)
        return BrokenWriter(stream) if path.parent==root and args and args[0]=='xb' else stream
    monkeypatch.setattr(Path,'open',failing_open)
    with pytest.raises(OSError,match='simulated full disk'):
        env[1].post(endpoint(row,'attachments'),data={'version':'1','files':(io.BytesIO(b'original'),'file.pdf')})
    assert list(root.iterdir())==[] and MaterialAttachment.query.count()==0
    record=db.session.get(MaterialRecord,row['id'])
    assert record.version==1 and record.status=='draft'


def test_invalid_csv_quote_is_rejected(env):
    login(env[1],env[2]['student'])
    csv_bytes=b'course_code,course_name,credits,score,full_score\nA,Math,2,80,"100'
    response=env[1].post('/api/materials/academic/parse-csv',data={
        'term':'2026','file':(io.BytesIO(csv_bytes),'grades.csv')})
    assert response.status_code==400
