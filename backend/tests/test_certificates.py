"""证书申请的完整 HTTP→队列→材料处理→权限回读流程。"""
import io
import json
import os
from datetime import timedelta
from pathlib import Path
import pytest
from PIL import Image
from extensions import db
from models import Application, Student, SystemSettings
from automation_models import utcnow
from certificate_models import CertificateAssessment
from conftest import login
from services.certificates.worker import run_one_certificate
from services.certificates.service import enqueue, contained, artifact_root

FIXTURES = Path(__file__).parent / 'fixtures' / 'lanqiao'


def submit(env, key='lanqiao', payload=None, filename='certificate.jpg', **extra):
    app, client, users = env
    if not SystemSettings.query.first():
        db.session.add(SystemSettings())
        db.session.commit()
    login(client, users['student'])
    student = Student.query.filter_by(student_id='S1').one()
    data = dict(studentId='S1', facultyId=student.faculty_id, departmentId=student.department_id,
                majorId=student.major_id, name='张三', projectName='蓝桥杯', applicationType='academic',
                status='pending', selfScore=2, certificateProject=key, certificateClaims={'award':'二等奖'})
    data.update(extra)
    if payload is None:
        payload = (FIXTURES / 'example4.jpg').read_bytes()
    return client.post('/api/applications', data={'application':json.dumps(data), 'files':(io.BytesIO(payload), filename)})


class NoWatermark:
    def __init__(self): self.calls = 0
    def predict(self, path):
        self.calls += 1
        return {'rec_texts':['学校名称：厦门大学','姓名：张三'], 'rec_scores':[.99,.99],
                'rec_polys':[[[10,10],[200,10],[200,30],[10,30]],[[10,50],[200,50],[200,70],[10,70]]]}


def assessment(env, response):
    assert response.status_code == 201, response.json
    return env[1].get(f"/api/certificates/applications/{response.json['id']}").json


def test_manual_has_no_queue_or_confidence(env):
    result = assessment(env, submit(env, 'manual'))
    assert result['status'] == 'manual'
    assert 'confidence' not in result['report']
    provider = NoWatermark()
    assert run_one_certificate(env[0], provider) is False
    assert provider.calls == 0
    assert CertificateAssessment.query.first().sources == []


def test_watermark_gate_keeps_original_and_never_second_ocr(env):
    response = submit(env)
    assessment(env, response)
    provider = NoWatermark()
    assert run_one_certificate(env[0], provider)
    result = env[1].get(f"/api/certificates/applications/{response.json['id']}").json
    assert provider.calls == 1
    assert result['status'] == 'manual_review'
    page = result['report']['pages'][0]
    assert page['watermark']['status'] == 'missing'
    assert 'processed' not in page['artifacts']
    assert result['authenticity'] == 'not_assessed'
    application = db.session.get(Application, response.json['id'])
    assert application.self_score == 2 and application.final_score is None and application.status == 'pending'
    row = CertificateAssessment.query.first()
    url = f"/api/certificates/applications/{application.id}/artifacts/{row.version}/{page['artifacts']['source']}"
    original = env[1].get(url)
    assert original.status_code == 200
    assert original.data == (FIXTURES/'example4.jpg').read_bytes()
    assert original.headers['Cache-Control'] == 'private, no-store'


def test_quality_reupload_skips_ocr(env):
    buffer = io.BytesIO()
    Image.new('RGB',(100,100),'white').save(buffer,format='PNG')
    response = submit(env, payload=buffer.getvalue(), filename='bad.png')
    assessment(env,response)
    provider = NoWatermark()
    run_one_certificate(env[0],provider)
    result = CertificateAssessment.query.first()
    assert result.status == 'needs_reupload' and provider.calls == 0


@pytest.mark.parametrize('payload,filename',[(b'corrupt','bad.jpg'),(b'other','material.pdf'),(b'hello','file.txt')])
def test_bad_material_is_explicit_manual_not_false_success(env,payload,filename):
    settings = SystemSettings(allowed_file_types='.jpg,.pdf,.txt')
    db.session.add(settings); db.session.commit()
    response = submit(env,payload=payload,filename=filename)
    assessment(env,response)
    provider = NoWatermark()
    run_one_certificate(env[0],provider)
    assert CertificateAssessment.query.first().status == 'manual_review'
    assert provider.calls == 0


def test_identity_whitelist_and_permissions(env):
    assert submit(env,key='unknown').status_code == 400
    assert submit(env,studentId='someone_else').status_code == 403
    response = submit(env)
    report = assessment(env,response)
    url = f"/api/certificates/applications/{response.json['id']}"
    login(env[1],env[2]['other'])
    assert env[1].get(url).status_code == 403
    row = CertificateAssessment.query.first()
    assert env[1].get(url+f"/artifacts/{row.version}/{row.sources[0]['relative']}").status_code == 403
    login(env[1],env[2]['admin'])
    assert env[1].get(url).status_code == 200
    login(env[1],env[2]['student'])
    assert env[1].post(f"/api/applications/{response.json['id']}/review",json={'status':'approved'}).status_code == 403
    assert env[1].put(f"/api/applications/{response.json['id']}",json={'finalScore':100}).status_code == 400
    assert env[1].get(url+f"/artifacts/{report['version']}/../../config.py").status_code == 404


def test_retry_version_and_expired_lease(env):
    response = submit(env)
    result = assessment(env,response)
    url = f"/api/certificates/applications/{response.json['id']}"
    assert env[1].post(url+'/retry',json={'version':result['version']}).status_code == 409
    row = CertificateAssessment.query.first()
    row.status, row.lease_until, row.lease_token = 'processing', utcnow()-timedelta(seconds=1), 'old-token'
    db.session.commit()
    run_one_certificate(env[0],NoWatermark())
    db.session.refresh(row)
    assert row.status == 'manual_review'
    assert env[1].post(url+'/retry',json={'version':-1}).status_code == 409
    retried = env[1].post(url+'/retry',json={'version':row.version})
    assert retried.status_code == 202 and retried.json['version'] > result['version']
    assert retried.json['report'] is None and retried.json['status'] == 'queued'


def test_old_worker_cannot_overwrite_updated_submission(env):
    response = submit(env)
    result = assessment(env,response)
    class Superseded(NoWatermark):
        def predict(self,path):
            app = db.session.get(Application,response.json['id'])
            enqueue(app,'manual',{})
            db.session.commit()
            return super().predict(path)
    run_one_certificate(env[0],Superseded())
    row = CertificateAssessment.query.first()
    db.session.refresh(row)
    assert row.project_key == 'manual' and row.status == 'manual' and row.version > result['version']
    assert 'pages' not in row.report


def test_updated_claims_requeue_and_discard_old_result(env):
    response = submit(env)
    assessment(env,response)
    run_one_certificate(env[0],NoWatermark())
    old_version = CertificateAssessment.query.first().version
    result = env[1].put(f"/api/applications/{response.json['id']}",json={
        'certificateProject':'lanqiao','certificateClaims':{'award':'三等奖'}})
    assert result.status_code == 200, result.json
    row = CertificateAssessment.query.first(); db.session.refresh(row)
    assert row.status == 'queued' and row.report is None and row.version > old_version
    assert row.claims['award'] == '三等奖'


def test_snapshot_tampering_stops_model(env):
    response = submit(env)
    assessment(env,response)
    row = CertificateAssessment.query.first()
    contained(artifact_root(),row.artifact_key+'/'+row.sources[0]['relative']).write_bytes(b'tampered')
    provider=NoWatermark()
    run_one_certificate(env[0],provider)
    assert provider.calls == 0
    assert '校验失败' in CertificateAssessment.query.first().report['pages'][0]['message']


def test_edit_adds_new_file_without_losing_retained_evidence(env):
    response = submit(env)
    assessment(env,response)
    application = db.session.get(Application,response.json['id'])
    original = list(application.files)
    result = env[1].put(f"/api/applications/{application.id}",data={
        'application':json.dumps({'files':original,'certificateProject':'lanqiao','certificateClaims':{}}),
        'files[1]':(io.BytesIO((FIXTURES/'example5.jpg').read_bytes()),'second.jpg')})
    assert result.status_code == 200,result.json
    db.session.refresh(application)
    assert len(application.files) == 2 and application.files[0] == original[0]
    row = CertificateAssessment.query.first(); db.session.refresh(row)
    assert len(row.sources) == 2 and row.status == 'queued'


def test_teacher_can_review_without_ocr_modifying_score(env):
    response=submit(env)
    assessment(env,response)
    provider=NoWatermark(); run_one_certificate(env[0],provider)
    application_id=response.json['id']
    login(env[1],env[2]['admin'])
    reviewed=env[1].post(f'/api/applications/{application_id}/review',json={
        'status':'approved','finalScore':1.25,'reviewComment':'已人工核验','reviewedBy':'管理员'})
    assert reviewed.status_code == 200,reviewed.json
    application=db.session.get(Application,application_id)
    db.session.refresh(application)
    assert application.final_score == 1.25 and application.self_score == 2
    login(env[1],env[2]['student'])
    assert env[1].put(f'/api/applications/{application_id}',json={'certificateProject':'lanqiao'}).status_code == 409


def test_certificate_migration_matches_model_and_is_reversible(env):
    import importlib.util
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    migration=Path(__file__).parents[1]/'migrations/versions/20261013_certificate_assessment.py'
    spec=importlib.util.spec_from_file_location('certificate_migration',migration)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    with db.engine.begin() as connection:
        CertificateAssessment.__table__.drop(connection)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            inspector=inspect(connection)
            assert {c['name'] for c in inspector.get_columns('certificate_assessment')} == {c.name for c in CertificateAssessment.__table__.columns}
            assert any(i['name']=='ix_certificate_queue' for i in inspector.get_indexes('certificate_assessment'))
            module.downgrade()
            assert not inspect(connection).has_table('certificate_assessment')
            module.upgrade()


def test_pdf_page_limit_stops_before_model(env):
    pdf=io.BytesIO()
    image=Image.new('RGB',(600,600),'white')
    image.save(pdf,format='PDF',save_all=True,append_images=[image]*4)
    response=submit(env,payload=pdf.getvalue(),filename='long.pdf')
    assessment(env,response)
    provider=NoWatermark(); run_one_certificate(env[0],provider)
    assert provider.calls==0
    assert 'PDF' in CertificateAssessment.query.first().report['pages'][0]['message']


@pytest.mark.skipif(os.environ.get('RUN_REAL_OCR') != '1',reason='设置 RUN_REAL_OCR=1 运行本项目真实证书模型')
def test_real_standalone_certificates_and_pdf(env):
    import paddleocr
    from services.recognition.provider import PaddleProvider
    assert 'pr_assistant' in str(Path(paddleocr.__file__).resolve())
    provider = PaddleProvider()
    expected = json.loads((FIXTURES/'expected.json').read_text(encoding='utf-8'))
    outputs = []
    for filename in ('example4.jpg','example5.jpg'):
        response = submit(env,payload=(FIXTURES/filename).read_bytes(),filename=filename)
        assessment(env,response)
        run_one_certificate(env[0],provider)
        row=CertificateAssessment.query.filter_by(application_id=response.json['id']).first()
        db.session.refresh(row)
        assert row.status in ('manual_review','recognized'), row.error or row.report
        page=row.report['pages'][0]
        assert page['watermark']['watermark_status']=='matched',page
        assert page['processed_fields']==expected[filename],page['processed_fields']
        assert page['authenticity']=='not_assessed'
        assert page['artifacts']['processed']
        outputs.append(row.report)
    # 扫描 PDF 也使用主项目渲染与同一门控，保留 PDF 原件。
    pdf=io.BytesIO()
    with Image.open(FIXTURES/'example5.jpg') as image:
        image.convert('RGB').save(pdf,format='PDF',resolution=150)
    response=submit(env,payload=pdf.getvalue(),filename='certificate.pdf')
    assessment(env,response)
    run_one_certificate(env[0],provider)
    row=CertificateAssessment.query.filter_by(application_id=response.json['id']).first()
    db.session.refresh(row)
    assert row.status in ('manual_review','recognized'),row.report
    page=row.report['pages'][0]
    assert page['watermark']['watermark_status']=='matched',page
    assert page['processed_fields']['certificate_no']==expected['example5.jpg']['certificate_no'],page
    outputs.append(row.report)
    folder=Path(__file__).parent/'artifacts'
    folder.mkdir(exist_ok=True)
    (folder/'real_certificate_preview.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2),encoding='utf-8')
