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
from services.automation import actor
from .service import artifact_root, contained

FIELDS = ('school', 'student', 'teacher', 'edition', 'track', 'group', 'region', 'award', 'certificate_no', 'date')


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


def save_preview(row, application, payload):
    user = actor()
    if user.role != 'student' or user.student_id != application.student_id:
        abort(403, description='仅学生本人可确认识别材料')
    if not row or not row.claims.get('preview_flow'):
        abort(409, description='不是上传预览申请')
    if application.status != 'draft' or row.status in ('queued', 'processing'):
        abort(409, description='申请已提交或识别尚未完成，请刷新状态')
    if not row.report or not row.report.get('pages'):
        abort(409, description='没有可确认的识别结果，请重新上传材料')
    if not isinstance(payload, dict) or set(payload) - {'version', 'project_name', 'award_date', 'rule_id', 'student_values', 'submit'}:
        abort(400, description='确认字段无效')
    if type(payload.get('version')) is not int or payload['version'] <= 0 or type(payload.get('submit')) is not bool:
        abort(400, description='必须提供版本和提交状态')
    values = payload.get('student_values')
    pages = row.report['pages']
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
    raw_date = payload.get('award_date')
    try:
        if not isinstance(raw_date, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw_date):
            raise ValueError()
        award_date = date.fromisoformat(raw_date)
    except ValueError:
        abort(400, description='获得日期格式无效')
    rule_id = payload.get('rule_id')
    if type(rule_id) is not int:
        abort(400, description='请选择有效竞赛规则')
    rule = db.session.get(Rule, rule_id)
    if not rule or rule.status != 'active' or rule.faculty_id not in (None, application.faculty_id) or rule.type != 'academic' or rule.sub_type != 'competition':
        abort(400, description='规则不是本学院可用的竞赛规则')
    if payload['submit']:
        settings = SystemSettings.query.first()
        now = datetime.now(pytz.timezone('Asia/Shanghai')).replace(tzinfo=None)
        if settings and (settings.system_status != 'online' or
            (settings.application_start and now < settings.application_start.replace(tzinfo=None)) or
            (settings.application_end and now > settings.application_end.replace(tzinfo=None))):
            abort(409, description='当前不在申请开放时间')
    # CAS both records in one transaction; retry/stale tabs cannot overwrite a submitted snapshot.
    changed = CertificateAssessment.query.filter_by(id=row.id, version=payload['version']).filter(
        CertificateAssessment.status.notin_(['queued', 'processing'])).update(
            {'version': CertificateAssessment.version + 1,
             'claims': {**row.claims, 'student_values': values}}, synchronize_session=False)
    if not changed:
        abort(409, description='版本已变化，请重新读取预览')
    changed = Application.query.filter_by(id=application.id, status='draft').update({
        'project_name': name.strip(), 'award_date': award_date, 'rule_id': rule.id,
        'application_type': 'academic', 'status': 'pending' if payload['submit'] else 'draft',
        'description': '学生已确认OCR预览；申报值与OCR结果独立保存'}, synchronize_session=False)
    if not changed:
        db.session.rollback()
        abort(409, description='申请状态已变化')
    db.session.commit()
    db.session.refresh(row)
    return row
