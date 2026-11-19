"""Confirmation must preserve the draft when evidence needs replacement."""
import io
from copy import deepcopy

import pytest
from PIL import Image

from certificate_models import CertificateAssessment
from conftest import login

pytestmark = pytest.mark.usefixtures("active_cycle")
from extensions import db
from models import Rule
from services.certificates.preview import FIELDS
from services.certificates.service import artifact_root, contained
from services.certificates.worker import run_one_certificate
from test_certificate_preview import ready
from test_certificates import NoWatermark


def reject_without_changes(env, row, data, message):
    before = deepcopy((row.version, row.claims, row.report, row.sources,
        row.application.status, row.application.project_name, row.application.award_date,
        row.application.rule_id, row.application.description))
    response = env[1].post(
        f'/api/certificates/applications/{row.application_id}/confirm-preview', json=data)
    assert response.status_code == 409, response.json
    assert message in response.json['error']
    db.session.refresh(row)
    db.session.refresh(row.application)
    assert (row.version, row.claims, row.report, row.sources,
        row.application.status, row.application.project_name, row.application.award_date,
        row.application.rule_id, row.application.description) == before


@pytest.mark.parametrize('submit', [False, True])
def test_actual_low_resolution_requires_reupload_before_confirmation(env, submit):
    login(env[1], env[2]['student'])
    image = io.BytesIO()
    Image.new('RGB', (100, 100), 'white').save(image, format='PNG')
    image.seek(0)
    uploaded = env[1].post('/api/certificates/previews', data={'files': (image, 'tiny.png')})
    assert uploaded.status_code == 202
    provider = NoWatermark()
    assert run_one_certificate(env[0], provider)
    row = db.session.get(CertificateAssessment, uploaded.json['id'])
    db.session.refresh(row)
    assert row.status == 'needs_reupload' and provider.calls == 0
    rule = Rule(name='Competition', type='academic', sub_type='competition', score=5,
                faculty_id=row.application.faculty_id, status='active')
    db.session.add(rule)
    db.session.commit()
    data = {'version': row.version, 'project_name': '低分辨率证书', 'award_date': '2026-10-01',
            'rule_id': rule.id, 'submit': submit,
            'student_values': [{field: '' for field in FIELDS} for _ in row.report['pages']]}
    reject_without_changes(env, row, data, '质量不合格')
    # The generic application endpoint must not bypass confirmation either.
    assert env[1].put(f'/api/applications/{row.application_id}',
                     json={'status': 'pending'}).status_code == 409


@pytest.mark.parametrize('marker', ['row', 'report', 'page', 'quality'])
def test_quality_flags_cannot_be_hidden_by_other_aggregate_states(env, marker):
    row, data = ready(env)
    report = deepcopy(row.report)
    report['pages'].append(deepcopy(report['pages'][0]))
    data['student_values'].append(deepcopy(data['student_values'][0]))
    if marker == 'row':
        row.status = 'needs_reupload'
    elif marker == 'report':
        report['status'] = 'needs_reupload'
    elif marker == 'page':
        report['pages'][1]['status'] = 'needs_reupload'
    else:
        report['pages'][1]['quality']['acceptable'] = False
    row.report = report
    db.session.commit()
    reject_without_changes(env, row, data, '质量不合格')


@pytest.mark.parametrize('submit', [False, True])
@pytest.mark.parametrize('problem', ['changed', 'missing', 'digest', 'path', 'no_sources', 'too_large'])
def test_original_integrity_errors_reject_confirmation_atomically(env, submit, problem):
    row, data = ready(env)
    data['submit'] = submit
    path = contained(contained(artifact_root(), row.artifact_key), row.sources[0]['relative'])
    if problem == 'changed':
        content = bytearray(path.read_bytes())
        content[len(content) // 2] ^= 1  # Same size: this must check content, not only file size.
        path.write_bytes(content)
    elif problem == 'missing':
        path.unlink()
    elif problem == 'digest':
        row.sources = [{**row.sources[0], 'sha256': 'invalid'}]
    elif problem == 'path':
        row.sources = [{**row.sources[0], 'relative': '../outside.jpg'}]
    elif problem == 'no_sources':
        row.sources = []
    else:
        env[0].config['CERTIFICATE_MAX_FILE_BYTES'] = path.stat().st_size - 1
    db.session.commit()
    reject_without_changes(env, row, data, '原件完整性校验失败')


def test_all_uploaded_originals_are_checked(env):
    row, data = ready(env)
    # Add a second real uploaded source to the evidence manifest and OCR snapshot.
    root = contained(artifact_root(), row.artifact_key)
    source = deepcopy(row.sources[0])
    source['relative'] = 'original-1.jpg'
    (root / source['relative']).write_bytes((root / row.sources[0]['relative']).read_bytes())
    row.sources = [*row.sources, source]
    report = deepcopy(row.report)
    report['pages'].append(deepcopy(report['pages'][0]))
    row.report = report
    data['student_values'].append(deepcopy(data['student_values'][0]))
    db.session.commit()
    (root / source['relative']).write_bytes(b'changed second original')
    reject_without_changes(env, row, data, '原件完整性校验失败')


def test_submit_rechecks_integrity_after_successfully_saving_draft(env):
    row, data = ready(env)
    data['submit'] = False
    response = env[1].post(
        f'/api/certificates/applications/{row.application_id}/confirm-preview', json=data)
    assert response.status_code == 200, response.json
    data.update(version=response.json['version'], submit=True)
    path = contained(contained(artifact_root(), row.artifact_key), row.sources[0]['relative'])
    path.write_bytes(b'changed after saving draft')
    reject_without_changes(env, row, data, '原件完整性校验失败')
