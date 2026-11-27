"""Compatibility applications retain an append-only stage audit in their row."""
import hashlib
import json

from automation_models import utcnow
from domain.review_stages import REVIEWER_ROLES, can_review_stage
from extensions import db
from models import Application
from services.time_format import utc_timestamp


def _fail(status_code, *, description):
    from use_cases.materials import MaterialUseCaseError
    raise MaterialUseCaseError(description, code='forbidden' if status_code == 403 else
                               'version_conflict' if status_code == 409 else 'invalid', status_code=status_code)


def begin_review(user, application, payload):
    """Claim one version; return (result, token). None result means final review."""
    if not isinstance(payload, dict):
        _fail(400, description='审核数据必须为对象')
    if user.faculty_id is None or user.faculty_id != application.faculty_id:
        _fail(403, description='只能审核本学院申请')
    decision = payload.get('status')
    if decision not in {'approved', 'rejected', 'needs_correction'}:
        _fail(400, description='无效审核结论')
    if user.role in REVIEWER_ROLES and set(payload) - {'status', 'reviewComment', 'review_version', 'version', 'idempotency_key', 'items'}:
        _fail(400, description='预审不能修改分数、规则或身份字段')
    version = payload.get('review_version', application.review_version)
    if type(version) is not int or version < 1:
        _fail(400, description='审核版本必须为正整数')
    comment = payload.get('reviewComment', '')
    if not isinstance(comment, str) or len(comment) > 2000 or (decision != 'approved' and not comment.strip()):
        _fail(400, description='退回须填写原因，审核意见不得超过2000字')
    key = payload.get('idempotency_key') or f'legacy:{user.id}:{version}'
    if not isinstance(key, str) or not 1 <= len(key) <= 128:
        _fail(400, description='幂等键无效')
    digest = hashlib.sha256(json.dumps([user.id, payload], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    history = list(application.review_history or [])
    previous = next((e for e in history if e.get('idempotency_key') == key), None)
    if previous:
        if previous['digest'] != digest or previous['actor']['id'] != user.id:
            _fail(409, description='幂等键冲突')
        return {**previous['result'], 'replayed': True}, None
    if not can_review_stage(user.role, user.faculty_id, application.faculty_id, application.review_stage):
        _fail(403, description='申请尚未流转至当前账号的审核阶段')
    if application.status != 'pending':
        _fail(409, description='仅待审核申请可审核')
    if version != application.review_version:
        _fail(409, description='审核版本已变化，请刷新')
    stage = application.review_stage
    updated = Application.query.filter_by(id=application.id, status='pending',
        review_stage=stage, review_version=version).update({
            'review_version': version + 1,
        }, synchronize_session=False)
    if updated != 1:
        _fail(409, description='申请已被其他审核员处理，请刷新')
    db.session.refresh(application)
    token = {'idempotency_key': key, 'digest': digest, 'review_stage': stage,
             'actor': {'id': user.id, 'name': user.name, 'role': user.role},
             'decision': 'approve' if decision == 'approved' else 'return',
             'comment': comment.strip(), 'created_at': utc_timestamp(utcnow())}
    if user.role in REVIEWER_ROLES:
        application.status = 'pending' if decision == 'approved' else 'needs_correction'
        if decision == 'approved':
            application.review_stage = stage + 1
        application.review_comment = comment.strip()
        application.reviewed_by = user.name
        application.reviewed_at = utcnow()
        from material_models import MaterialRecord
        linked = MaterialRecord.query.filter_by(application_id=application.id).first()
        if linked is not None and (linked.analysis or {}).get('source') == 'certificate_preview_compatibility':
            from use_cases.materials import _cas_change
            _cas_change(linked, linked.version, ('submitted', 'under_review'), {
                'review_stage': application.review_stage,
                'status': 'submitted' if decision == 'approved' else 'needs_correction',
            })
        result = {'application_id': application.id, 'status': application.status,
                  'review_stage': application.review_stage, 'review_version': application.review_version,
                  'scoring': None, 'replayed': False}
        finish_review(application, token, result)
        return result, None
    return None, token


def finish_review(application, token, result):
    if token is not None:
        application.review_history = [*(application.review_history or []), {**token, 'result': result}]


def public_history(application):
    return [{k: v for k, v in event.items() if k not in {'digest', 'idempotency_key', 'result'}}
            for event in application.review_history or []]
