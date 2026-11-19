import io
from copy import deepcopy
from pathlib import Path
import pytest

pytestmark = pytest.mark.usefixtures("active_cycle")
from extensions import db
from models import Application, Rule, Student, User
from certificate_models import CertificateAssessment
from conftest import login
from test_certificates import NoWatermark
from services.certificates.worker import run_one_certificate
from services.certificates.preview import FIELDS
from use_cases.rule_versions import publish_rule_version
from workflow_models import ScoreEntry, StudentScoreSnapshot


def upload(env):
    app, client, users = env
    login(client, users['student'])
    return client.post('/api/certificates/previews', data={'files': (
        io.BytesIO((Path(__file__).parent / 'fixtures/lanqiao/example4.jpg').read_bytes()), 'sample.jpg')})


def ready(env):
    response = upload(env)
    assert response.status_code == 202, response.json
    assert run_one_certificate(env[0], NoWatermark())
    row = db.session.get(CertificateAssessment, response.json['id'])
    db.session.refresh(row)
    rule = Rule(name='Test competition', type='academic', sub_type='competition', score=5,
                faculty_id=row.application.faculty_id, status='active')
    db.session.add(rule); db.session.commit()
    data = {'version': row.version, 'project_name':'蓝桥杯测试', 'award_date':'2026-10-01',
            'rule_id':rule.id, 'submit':True,
            'student_values':[{field: ('学生修正姓名' if field=='student' else str(page.get('raw_fields',{}).get(field) or '')) for field in FIELDS} for page in row.report['pages']]}
    for fields in data['student_values']:
        fields['date'] = '2026年10月1日'
    return row, data


def test_upload_before_application_fields_and_block_early_submit(env):
    response=upload(env)
    assert response.status_code==202
    row=db.session.get(CertificateAssessment,response.json['id'])
    assert row.application.status=='draft' and row.status=='queued'
    assert row.sources and row.application.files==[]
    response=env[1].post(f'/api/certificates/applications/{row.application_id}/confirm-preview',json={})
    assert response.status_code==409


def test_confirm_preserves_ocr_and_original_then_teacher_reads_both(env):
    row,data=ready(env)
    report,sources,key=deepcopy(row.report),deepcopy(row.sources),row.artifact_key
    url=f'/api/certificates/applications/{row.application_id}'
    response=env[1].post(url+'/confirm-preview',json=data)
    assert response.status_code==200, response.json
    assert response.json['application_status']=='pending'
    assert response.json['student_values'][0]['student']=='学生修正姓名'
    db.session.refresh(row)
    assert row.report==report and row.sources==sources and row.artifact_key==key
    assert row.status!='queued' and row.application.final_score is None
    assert env[1].post(url+'/confirm-preview',json=data).status_code==409
    assert env[1].post(url+'/retry',json={'version':row.version}).status_code==409
    login(env[1],env[2]['admin'])
    fetched=env[1].get(url)
    assert fetched.status_code==200 and fetched.json['report']==report
    assert env[1].get(url+f'/artifacts/{row.version}/'+sources[0]['relative']).status_code==200
    login(env[1],env[2]['other'])
    assert env[1].get(url).status_code==403


def test_student001_full_certificate_scoring_acceptance(env):
    """证明材料确认、教师核验、权威计分与学生展示形成一条闭环。"""
    student = Student.query.filter_by(student_id='S1').one()
    student_user = db.session.get(User, env[2]['student'])
    student.student_id = 'student001'
    student_user.student_id = 'student001'
    student_user.username = 'student001'
    db.session.commit()

    response = upload(env)
    assert response.status_code == 202, response.json
    assert run_one_certificate(env[0], NoWatermark())
    assessment = db.session.get(CertificateAssessment, response.json['id'])
    db.session.refresh(assessment)

    admin = db.session.get(User, env[2]['admin'])
    rule = Rule(name='蓝桥杯一等奖', type='academic', sub_type='competition', score=5,
                max_score=5, faculty_id=student.faculty_id, status='active')
    db.session.add(rule)
    publish_rule_version(rule, published_by=admin, cycle_code=2026)
    db.session.commit()
    student_values = [
        {field: str(page.get('raw_fields', {}).get(field) or '') for field in FIELDS}
        for page in assessment.report['pages']
    ]
    for fields in student_values:
        fields['date'] = '2024年5月1日'
    confirmed = env[1].post(
        f'/api/certificates/applications/{assessment.application_id}/confirm-preview',
        json={'version': assessment.version, 'project_name': '蓝桥杯一等奖',
              'award_date': '2024-05-01', 'rule_id': rule.id,
              'student_values': student_values, 'submit': True},
    )
    assert confirmed.status_code == 200, confirmed.json

    login(env[1], admin.id)
    reviewed = env[1].post(
        f'/api/applications/{assessment.application_id}/review',
        json={'status': 'approved', 'reviewComment': '仅核验原件，采用规则自动分',
              'idempotency_key': 'student001-lanqiao-acceptance'},
    )
    assert reviewed.status_code == 200, reviewed.json
    assert reviewed.json['overall_status'] == 'complete'
    assert reviewed.json['verification_status'] == 'verified'
    assert reviewed.json['scoring_status'] == 'scored'
    entry = ScoreEntry.query.filter_by(student_id='student001').one()
    snapshot = StudentScoreSnapshot.query.filter_by(
        student_id='student001', year=2026, status='current').one()
    assert entry.effective_score == 5
    assert snapshot.specialty_raw_score == 5

    login(env[1], student_user.id)
    current = env[1].get('/api/workflow/students/student001/score/current')
    assert current.status_code == 200, current.json
    assert current.json['entries'][0]['included_score'] == '5.0000'
    assert current.json['categories']['academic']['effective_score'] == '5.0000'


def test_confirmed_ocr_date_is_authoritative_and_conflict_is_atomic(env):
    row, data = ready(env)
    application = row.application
    original_claims = deepcopy(row.claims)
    data['award_date'] = '2026-11-12'
    for fields in data['student_values']:
        fields['date'] = '2026年5月8日'
    url = f'/api/certificates/applications/{row.application_id}/confirm-preview'

    conflict = env[1].post(url, json=data)
    assert conflict.status_code == 409
    assert conflict.json['code'] == 'award_date_confirmation_conflict'
    db.session.refresh(row); db.session.refresh(application)
    assert row.version == data['version'] and row.claims == original_claims
    assert application.status == 'draft' and application.award_date is None

    data['award_date'] = '2026-05-08'
    accepted = env[1].post(url, json=data)
    assert accepted.status_code == 200, accepted.json
    db.session.refresh(row); db.session.refresh(application)
    assert application.award_date.isoformat() == '2026-05-08'
    assert row.claims['confirmed_terms']['award_date'] == '2026年5月8日'
    assert row.claims['normalized_terms']['award_date'] == '2026-05-08'
    assert row.claims['ocr_raw_terms']
    assert row.claims['confirmation_history'][-1]['actor_id'] == env[2]['student']
    fetched = env[1].get(f'/api/certificates/applications/{row.application_id}')
    assert fetched.json['confirmed_terms']['award_date'] == '2026年5月8日'
    assert fetched.json['normalized_terms']['award_date'] == '2026-05-08'
    assert fetched.json['normalization_version'] == 'material-terms-v1'


def test_ocr_result_alone_never_confirms_submits_or_selects_rule(env):
    response = upload(env)
    assert response.status_code == 202
    assert run_one_certificate(env[0], NoWatermark())
    row = db.session.get(CertificateAssessment, response.json['id'])
    fetched = env[1].get(f'/api/certificates/applications/{row.application_id}')
    assert fetched.status_code == 200
    assert fetched.json['report']['pages']
    assert fetched.json['confirmed_terms'] is None
    assert fetched.json['normalized_terms'] is None
    assert fetched.json['confirmation_history'] == []
    assert row.application.status == 'draft'
    assert row.application.rule_id is None and row.application.award_date is None


def test_saved_draft_roundtrip_and_stale_version(env):
    row,data=ready(env);data['submit']=False
    url=f'/api/certificates/applications/{row.application_id}/confirm-preview'
    response=env[1].post(url,json=data)
    assert response.status_code==200 and response.json['application_status']=='draft'
    assert env[1].post(url,json=data).status_code==409
    data['version']=response.json['version'];data['submit']=True
    assert env[1].post(url,json=data).status_code==200


def test_preview_rejects_staff_upload_legacy_edit_and_invalid_fields(env):
    row,data=ready(env)
    id=row.application_id
    assert env[1].put(f'/api/applications/{id}',json={'projectName':'不允许覆盖'}).status_code==409
    data['student_values'][0]['student']=123
    assert env[1].post(f'/api/certificates/applications/{id}/confirm-preview',json=data).status_code==400
    login(env[1],env[2]['admin'])
    assert env[1].post('/api/certificates/previews').status_code==403
    assert env[1].post(f'/api/applications/{id}/review',json={'status':'approved','finalScore':5}).status_code==409


def test_bad_upload_leaves_no_draft_or_files(env):
    login(env[1],env[2]['student'])
    response=env[1].post('/api/certificates/previews',data={'files':(io.BytesIO(b'x'),'bad.exe')})
    assert response.status_code==400
    assert Application.query.count()==0
    folder=Path(env[0].config['CERTIFICATE_STORAGE_FOLDER'])
    assert not list(folder.iterdir())


@pytest.mark.skipif(__import__('os').environ.get('RUN_REAL_OCR') != '1', reason='需要本地真实OCR模型')
def test_real_preview_declaration_and_review(env):
    import os
    from services.recognition.provider import PaddleProvider
    response = upload(env)
    assert response.status_code == 202
    assert run_one_certificate(env[0], PaddleProvider(os.environ.get('OCR_MODEL_ROOT')))
    row = db.session.get(CertificateAssessment, response.json['id'])
    db.session.refresh(row)
    assert row.status in ('recognized', 'manual_review'), row.error or row.report
    page = row.report['pages'][0]
    assert page.get('raw_fields', {}).get('student'), page
    original_report = deepcopy(row.report)
    rule = Rule(name='真实OCR测试竞赛', type='academic', sub_type='competition', score=5,
                faculty_id=row.application.faculty_id, status='active')
    db.session.add(rule)
    publish_rule_version(rule,published_by=db.session.get(User,env[2]['admin']),cycle_code=2026)
    db.session.commit()
    values = [{key: str(p.get('processed_fields', {}).get(key) or p.get('raw_fields', {}).get(key) or '') for key in FIELDS} for p in row.report['pages']]
    values[0]['student'] = '学生自主修正'
    url = f'/api/certificates/applications/{row.application_id}'
    saved = env[1].post(url + '/confirm-preview', json={'version':row.version,
        'project_name':'蓝桥杯真实识别测试', 'award_date':None, 'rule_id':rule.id,
        'student_values':values, 'submit':True})
    assert saved.status_code == 200, saved.json
    teacher = User(username='preview_teacher', name='教师', password='test', role='teacher',
                   status='active', faculty_id=row.application.faculty_id)
    db.session.add(teacher); db.session.commit()
    login(env[1], teacher.id)
    read = env[1].get(url)
    assert read.json['student_values'][0]['student'] == '学生自主修正'
    assert read.json['report'] == original_report
    assert env[1].get(url + f'/artifacts/{read.json["version"]}/' + row.sources[0]['relative']).status_code == 200
    review = env[1].post(f'/api/applications/{row.application_id}/review', json={'status':'approved', 'idempotency_key':'real-legacy-preview-review', 'reviewComment':'已对照原件及申报值'})
    assert review.status_code == 200, review.json
    db.session.refresh(row)
    assert row.application.status == 'approved'
    assert row.report == original_report
