"""Recognize private materials before submission; retain OCR facts beside student declarations."""
import hashlib
import re
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path
import pytz
from flask import abort, current_app
from extensions import db
from models import Application, Student, Rule, SystemSettings
from certificate_models import CertificateAssessment
from automation_models import utcnow
from services.automation import actor
from domain.material_terms import (NORMALIZATION_VERSION, TermNormalizationError,
                                   normalize_confirmed_terms)
from .service import artifact_root, contained
from .fields import FIELDS


def _confirmed_terms(project_name, values):
    """Build one authoritative snapshot from student declarations, never OCR."""
    populated_dates = {fields['date'].strip() for fields in values if fields['date'].strip()}
    if len(populated_dates) != 1:
        abort(400, description={
            'error': '请确认唯一的获奖日期',
            'code': 'confirmed_award_date_required' if not populated_dates else 'confirmed_award_date_ambiguous',
        })
    def unique(field):
        entries = {item[field].strip() for item in values if item[field].strip()}
        return next(iter(entries)) if len(entries) == 1 else None
    confirmed = {
        'competition_name': project_name.strip(),
        'award_level': unique('award'),
        'competition_level': None,
        'region': unique('region'),
        'group': unique('group'),
        'track': unique('track'),
        'award_date': next(iter(populated_dates)),
    }
    try:
        normalized = normalize_confirmed_terms(confirmed)
    except TermNormalizationError as error:
        abort(400, description={
            'error': '学生确认的获奖日期格式无效',
            'code': error.reason,
            'field': error.field,
        })
    return confirmed, normalized


def _ocr_raw_terms(report):
    return [
        {field: page.get('raw_fields', {}).get(field) for field in FIELDS}
        for page in (report or {}).get('pages', [])
    ]


def create_preview(files):
    user = actor()
    if user.role != 'student':
        abort(403, description='仅学生可上传识别材料')
    student = Student.query.filter_by(student_id=user.student_id).first()
    if not student or not student.faculty_id or student.faculty_id != user.faculty_id:
        abort(403, description='学生学院资料不完整')
    if not 1 <= len(files) <= 10:
        abort(400, description='请选择1至10份证书材料')
    key = str(uuid.uuid4())
    folder = contained(artifact_root(), key)
    folder.mkdir(parents=True)
    try:
        sources = []
        for index, file in enumerate(files):
            name = (file.filename or '').replace('\\', '/').split('/')[-1]
            suffix = Path(name).suffix.lower()
            if suffix not in ('.jpg', '.jpeg', '.png', '.webp', '.pdf'):
                abort(400, description='证书仅支持JPG/PNG/WebP/PDF')
            limit = current_app.config.get('CERTIFICATE_MAX_FILE_BYTES', 10 * 1024 * 1024)
            payload = file.stream.read(limit + 1)
            if not payload or len(payload) > limit:
                abort(400, description='证书文件必须非空且不超过10MB')
            relative = f'original-{index}{suffix}'
            (folder / relative).write_bytes(payload)
            sources.append({'name': name, 'relative': relative, 'sha256': hashlib.sha256(payload).hexdigest()})
        application = Application(student_id=student.student_id, student_name=student.student_name,
            faculty_id=student.faculty_id, department_id=student.department_id, major_id=student.major_id,
            application_type='academic', status='draft', project_name='蓝桥杯识别草稿', files=[])
        db.session.add(application)
        db.session.flush()
        row = CertificateAssessment(application_id=application.id, project_key='lanqiao', status='queued',
            claims={'student': student.student_name, 'preview_flow': True}, sources=sources,
            artifact_key=key, version=1, attempts=0)
        db.session.add(row)
        db.session.commit()
        return row
    except Exception:
        db.session.rollback()
        shutil.rmtree(folder, ignore_errors=True)
        raise


def requires_reupload(row):
    report = row.report or {}
    return row.status == 'needs_reupload' or report.get('status') == 'needs_reupload' or any(
        page.get('status') == 'needs_reupload' or page.get('quality', {}).get('acceptable') is False
        for page in report.get('pages', []))


def verify_originals(row):
    """Check uploaded bytes again before confirming the OCR/student snapshot."""
    try:
        if not isinstance(row.sources, list) or not row.sources:
            raise ValueError('Missing sources')
        root = contained(artifact_root(), row.artifact_key)
        limit = current_app.config.get('CERTIFICATE_MAX_FILE_BYTES', 10 * 1024 * 1024)
        for source in row.sources:
            if not isinstance(source, dict):
                raise ValueError('Invalid source')
            relative, expected = source.get('relative'), source.get('sha256')
            if not isinstance(relative, str) or not isinstance(expected, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', expected):
                raise ValueError('Missing original digest')
            path = contained(root, relative)
            if not path.is_file():
                raise ValueError('Missing original')
            digest, size = hashlib.sha256(), 0
            with path.open('rb') as stream:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise ValueError('Original too large')
                    digest.update(chunk)
            if size == 0 or digest.hexdigest() != expected.lower():
                raise ValueError('Original digest mismatch')
    except (OSError, ValueError, TypeError):
        abort(409, description='证书原件完整性校验失败，文件缺失、已变化或校验信息无效，请重新上传材料并识别')


def _validate_confirmation(payload, pages, faculty_id):
    if not isinstance(payload, dict) or set(payload) - {'version', 'project_name', 'award_date', 'rule_id', 'student_values', 'submit'}:
        abort(400, description='确认字段无效')
    if type(payload.get('version')) is not int or payload['version'] <= 0 or type(payload.get('submit')) is not bool:
        abort(400, description='必须提供版本和提交状态')
    values = payload.get('student_values')
    if not isinstance(values, list) or len(values) != len(pages):
        abort(400, description='申报值必须覆盖每一页识别结果')
    for fields in values:
        if not isinstance(fields, dict) or set(fields) != set(FIELDS):
            abort(400, description='申报字段不完整')
        if any(not isinstance(v, str) or len(v) > 200 or '\x00' in v for v in fields.values()):
            abort(400, description='申报值必须为200字以内文字')
    name = payload.get('project_name')
    if not isinstance(name, str) or not 2 <= len(name.strip()) <= 30:
        abort(400, description='项目名称必须为2至30字')
    confirmed_terms, normalized_terms = _confirmed_terms(name, values)
    confirmed_date = normalized_terms['award_date']
    compatibility_date = payload.get('award_date')
    if compatibility_date not in (None, ''):
        try:
            compatibility_date = date.fromisoformat(compatibility_date).isoformat()
        except (TypeError, ValueError):
            abort(400, description={'error': '获得日期格式无效', 'code': 'invalid_award_date'})
        if compatibility_date != confirmed_date:
            abort(409, description={
                'error': '申请获奖日期与材料确认日期不一致，请重新确认',
                'code': 'award_date_confirmation_conflict',
                'application_award_date': compatibility_date,
                'confirmed_award_date': confirmed_date,
            })
    award_date = date.fromisoformat(confirmed_date)
    rule_id = payload.get('rule_id')
    if type(rule_id) is not int:
        abort(400, description='请选择有效竞赛规则')
    rule = db.session.get(Rule, rule_id)
    if not rule or rule.status != 'active' or rule.faculty_id not in (None, faculty_id) or rule.type != 'academic' or rule.sub_type != 'competition':
        abort(400, description='规则不是本学院可用的竞赛规则')
    return values, name.strip(), award_date, rule, confirmed_terms, normalized_terms


def _check_application_period():
    settings = SystemSettings.query.first()
    now = datetime.now(pytz.timezone('Asia/Shanghai')).replace(tzinfo=None)
    if settings and (settings.system_status != 'online' or
        (settings.application_start and now < settings.application_start.replace(tzinfo=None)) or
        (settings.application_end and now > settings.application_end.replace(tzinfo=None))):
        abort(409, description='当前不在申请开放时间')


def save_preview(row, application, payload):
    user = actor()
    if user.role != 'student' or user.student_id != application.student_id:
        abort(403, description='仅学生本人可确认识别材料')
    if not row or not row.claims.get('preview_flow'):
        abort(409, description='不是上传预览申请')
    if application.status != 'draft' or row.status in ('queued', 'processing'):
        abort(409, description='申请已提交或识别尚未完成，请刷新状态')
    if requires_reupload(row):
        abort(409, description='材料质量不合格，请重新上传清晰材料并完成识别后再确认或提交')
    if not row.report or not row.report.get('pages'):
        abort(409, description='没有可确认的识别结果，请重新上传材料')
    values, name, award_date, rule, confirmed_terms, normalized_terms = _validate_confirmation(payload, row.report['pages'], application.faculty_id)
    verify_originals(row)
    if payload['submit']:
        _check_application_period()
        from use_cases.cycles import pin_application_cycle
        policy = pin_application_cycle(application)
    else:
        policy = None
    # CAS both records in one transaction; retry/stale tabs cannot overwrite a submitted snapshot.
    changed = CertificateAssessment.query.filter_by(id=row.id, version=payload['version']).filter(
        CertificateAssessment.status.notin_(['queued', 'processing', 'needs_reupload'])).update(
            {'version': CertificateAssessment.version + 1,
             'claims': {**row.claims, 'student_values': values,
                        'ocr_raw_terms': _ocr_raw_terms(row.report),
                        'confirmed_terms': confirmed_terms,
                        'normalized_terms': normalized_terms,
                        'normalization_version': NORMALIZATION_VERSION,
                        'confirmation_history': [
                            *row.claims.get('confirmation_history', []),
                            {'actor_id': user.id, 'source_version': payload['version'],
                             'confirmed_at': utcnow().isoformat() + 'Z',
                             'submit': payload['submit'],
                             'confirmed_terms': confirmed_terms,
                             'normalized_terms': normalized_terms},
                        ]}}, synchronize_session=False)
    if not changed:
        abort(409, description='版本已变化，请重新读取预览')
    application_updates = {
        'project_name': name.strip(), 'award_date': award_date, 'rule_id': rule.id,
        'application_type': 'academic', 'status': 'pending' if payload['submit'] else 'draft',
        'description': '学生已确认OCR预览；申报值与OCR结果独立保存'}
    if policy:
        application_updates.update(
            cycle_code=policy.cycle_code, cycle_policy_version_id=policy.id
        )
    changed = Application.query.filter_by(id=application.id, status='draft').update(
        application_updates, synchronize_session=False)
    if not changed:
        db.session.rollback()
        abort(409, description='申请状态已变化')
    db.session.commit()
    db.session.refresh(row)
    return row
