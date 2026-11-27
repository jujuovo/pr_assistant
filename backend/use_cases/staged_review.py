"""Stage commands share the material transaction, version and audit ledger."""
import hashlib
import json

from extensions import db
from domain.review_stages import REVIEWER_ROLES, can_review_stage
from material_models import MaterialEvent
from workflow_models import MaterialReviewCommand


def assert_final_review(user, row):
    from use_cases.materials import MaterialUseCaseError
    if (user.role not in {'teacher', 'admin'} or
            not can_review_stage(user.role, user.faculty_id, row.faculty_id, row.review_stage)):
        raise MaterialUseCaseError('材料尚未流转至当前账号的审核阶段',
                                   code='review_stage_forbidden', status_code=403)


def stage_filter(query, model, user):
    from domain.review_stages import ROLE_STAGES
    if user.role in ROLE_STAGES:
        query = query.filter(model.review_stage == ROLE_STAGES[user.role])
    return query


def review_before_final(user, row, payload):
    """Return an intermediate result, or None to execute existing final scoring.

    No scores, verified facts or student declarations are written here. The
    caller commits the command, stage and audit event in the same transaction.
    """
    from use_cases.materials import MaterialUseCaseError, _cas_change
    from services.materials.schemas import integer, text
    if user.role not in REVIEWER_ROLES:
        assert_final_review(user, row)
        return None
    if user.faculty_id is None or user.faculty_id != row.faculty_id:
        raise MaterialUseCaseError('只能审核本学院材料', code='forbidden', status_code=403)
    if row.category == 'competition':
        from use_cases.materials import validate_competition_review_command
        validate_competition_review_command(user, row, payload)
    version = integer(payload.get('version'), 'version', 1, 2_000_000_000)
    decisions = {'approve', 'return'} if row.category == 'competition' else {'verified', 'rejected', 'needs_correction'}
    if payload.get('decision') not in decisions:
        raise MaterialUseCaseError('无效审核结论')
    approving = payload['decision'] in {'approve', 'verified'}
    comment = text(payload.get('comment', ''), '审核意见', required=not approving, maximum=2000)
    allowed = {'version', 'decision', 'comment', 'idempotency_key', 'ocr_confirmed', 'verified_facts'}
    if set(payload) - allowed:
        raise MaterialUseCaseError('预审不允许修改计分或规则字段')
    key = payload.get('idempotency_key') or f'stage:{user.id}:{version}'
    key = text(key, '幂等键', maximum=128)
    digest = hashlib.sha256(json.dumps([row.id, user.id, payload], sort_keys=True,
                                      ensure_ascii=False).encode()).hexdigest()
    previous = MaterialReviewCommand.query.filter_by(record_id=row.id, idempotency_key=key).first()
    if previous:
        if previous.request_digest != digest or previous.created_by != user.id:
            raise MaterialUseCaseError('幂等键冲突', code='idempotency_conflict', status_code=409)
        return {**previous.result, 'replayed': True}
    if not can_review_stage(user.role, user.faculty_id, row.faculty_id, row.review_stage):
        raise MaterialUseCaseError('材料尚未流转至当前账号的审核阶段', code='review_stage_forbidden', status_code=403)
    if row.status not in {'submitted', 'under_review'}:
        raise MaterialUseCaseError('材料不在可审核状态', code='review_not_available', status_code=409)
    from services.materials.originals import verify_ocr_originals
    verify_ocr_originals(row)
    old_stage = row.review_stage
    target = old_stage + 1 if approving else old_stage
    _cas_change(row, version, ('submitted', 'under_review'), {
        'review_stage': target, 'status': 'submitted' if approving else 'needs_correction',
    })
    result = {'record_id': row.id, 'id': row.id, 'version': row.version,
              'status': row.status, 'review_stage': target, 'decision': payload['decision'],
              'scoring': None, 'replayed': False}
    db.session.add(MaterialEvent(record_id=row.id, actor_id=user.id, action='stage_reviewed', details={
        'decision': 'approve' if approving else 'return', 'comment': comment,
        'review_stage': old_stage, 'next_review_stage': target if approving else None,
        'version': row.version, 'data_snapshot': row.data,
        'attachments_snapshot': [a.sha256 for a in row.attachments],
        'verified_facts': payload.get('verified_facts'),
    }))
    db.session.add(MaterialReviewCommand(record_id=row.id, idempotency_key=key,
        request_digest=digest, result=result, created_by=user.id))
    db.session.flush()
    return result
