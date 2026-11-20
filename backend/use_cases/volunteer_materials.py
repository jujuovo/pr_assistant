"""Official cumulative hours use the shared material review/score transaction."""
from extensions import db
from models import Faculty, Rule
from domain.volunteer_policy import POLICY_ID, SOURCE_SHA256
from use_cases.materials import MaterialUseCaseError, submit_material


def submit_volunteer(user, row, version):
    from use_cases.cycles import current_cycle_policy
    from use_cases.rule_versions import publish_rule_version
    policy = current_cycle_policy()
    if policy.cycle_code < 2028 or row.year != policy.cycle_code:
        raise MaterialUseCaseError('该办法自2028届实施，请填写当前推免周期', code='volunteer_cycle_mismatch')
    if not row.attachments:
        raise MaterialUseCaseError('请上传本次志愿服务工时证明')
    from workflow_models import ScoreEntry
    legacy = ScoreEntry.query.filter(
        ScoreEntry.student_id == row.student_id, ScoreEntry.year == policy.cycle_code,
        ScoreEntry.status == 'active', ScoreEntry.source_type != 'material',
        ScoreEntry.category.in_(['volunteer','volunteer_credit','volunteer_honor']),
    ).first()
    if legacy:
        raise MaterialUseCaseError('本周期已有旧志愿计分，请先由管理员核对迁移，避免重复计分',
                                   code='legacy_volunteer_reconciliation_required', status_code=409)
    # Serialize first creation per faculty. The published content is official,
    # fixed policy, not a student-selected rate or score.
    db.session.query(Faculty).filter_by(id=row.faculty_id).with_for_update().one()
    name = f'志愿服务累计工时（2025年2月办法，{policy.cycle_code}届）'
    rule = Rule.query.filter_by(name=name, faculty_id=row.faculty_id, sub_type='volunteer').first()
    if rule is None:
        rule = Rule(name=name, faculty_id=row.faculty_id, type='comprehensive',
                    sub_type='volunteer', score=0, max_score=1, status='active',
                    calculation_formula={'policy_id': POLICY_ID, 'source_sha256': SOURCE_SHA256})
        db.session.add(rule)
        db.session.flush()
        publish_rule_version(rule, cycle_code=policy.cycle_code)
    submit_material(user, row, version)


def appeal_volunteer(user, row, version, reason):
    from services.materials.schemas import text
    from services.volunteer_ocr import projection
    from domain.materials import ActorScope, MaterialScope, allowed_actions
    from use_cases.materials import _cas_change, _event
    from automation_models import utcnow
    scope = ActorScope(user.role, user.student_id, user.faculty_id)
    material = MaterialScope(row.student_id, row.faculty_id, row.status)
    _, actions = projection(row, user, allowed_actions(scope, material))
    if 'appeal' not in actions:
        raise MaterialUseCaseError('仅本人被OCR打回的当前材料可以申诉', code='appeal_not_available', status_code=409)
    reason = text(reason, '申诉理由', maximum=2000)
    appeal = {'reason': reason, 'actor_id': user.id, 'created_at': utcnow().isoformat()+'Z',
              'ocr_jobs': row.analysis['volunteer_ocr']['jobs'], 'from_version': row.version}
    _cas_change(row, version, ('needs_correction',), {
        'status': 'draft', 'analysis': {**row.analysis, 'volunteer_appeal': appeal}})
    _event(row, user, 'appealed', {**appeal, 'priority_review': True})
    submit_volunteer(user, row, row.version)
    return row
