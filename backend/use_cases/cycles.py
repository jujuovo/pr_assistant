"""Application use cases for the single global recommendation cycle."""

from automation_models import utcnow
from domain.cycles import CyclePolicyError, normalize_cycle_code
from extensions import db
from models import SystemSettings
from workflow_models import RecommendationCyclePolicy


class CycleUseCaseError(ValueError):
    def __init__(self, message, *, code="invalid_cycle_policy"):
        super().__init__(message)
        self.code = code


def _authorize_admin(user):
    if not user or user.role != "admin":
        raise CycleUseCaseError("仅管理员可管理推免周期", code="forbidden")


def _settings_for_update():
    settings = SystemSettings.query.order_by(SystemSettings.id).with_for_update().first()
    if settings is None:
        settings = SystemSettings()
        db.session.add(settings)
        db.session.flush()
    return settings


def current_cycle_policy(*, required=True, lock=False):
    query = RecommendationCyclePolicy.query.filter_by(active_marker=1)
    if lock:
        query = query.with_for_update()
    policy = query.first()
    if policy is None and required:
        raise CycleUseCaseError(
            "当前没有完整的活动推免周期政策", code="cycle_policy_missing"
        )
    return policy


def pin_application_cycle(application):
    """Attach the active policy once; existing historical ownership is preserved."""
    if application.cycle_code is not None and application.cycle_policy_version_id:
        return db.session.get(
            RecommendationCyclePolicy, application.cycle_policy_version_id
        )
    policy = current_cycle_policy(lock=True)
    application.cycle_code = policy.cycle_code
    application.cycle_policy_version_id = policy.id
    return policy


def pin_material_cycle(row):
    if row.cycle_policy_version_id:
        return db.session.get(RecommendationCyclePolicy, row.cycle_policy_version_id)
    application = None
    if getattr(row, "application_id", None):
        from legacy_models import Application
        application = db.session.get(Application, row.application_id)
    if application:
        policy = pin_application_cycle(application)
    else:
        policy = current_cycle_policy(lock=True)
    row.year = policy.cycle_code
    row.cycle_policy_version_id = policy.id
    return policy


def create_cycle_policy(user, cycle_code, start_date, end_date, display_name=None):
    _authorize_admin(user)
    try:
        code = normalize_cycle_code(cycle_code)
        digest = RecommendationCyclePolicy.canonical_digest(code, start_date, end_date)
    except (CyclePolicyError, AttributeError) as error:
        raise CycleUseCaseError(str(error)) from error
    if end_date < start_date:
        raise CycleUseCaseError("奖状有效期结束日期不能早于开始日期")
    existing = RecommendationCyclePolicy.query.filter_by(
        cycle_code=code, digest=digest
    ).first()
    if existing:
        return existing, False
    latest = (
        RecommendationCyclePolicy.query.filter_by(cycle_code=code)
        .order_by(RecommendationCyclePolicy.version.desc())
        .first()
    )
    policy = RecommendationCyclePolicy(
        cycle_code=code,
        version=(latest.version + 1 if latest else 1),
        display_name=(display_name or str(code)).strip(),
        eligible_award_start_date=start_date,
        eligible_award_end_date=end_date,
        boundary="inclusive",
        digest=digest,
        status="draft",
        active_marker=None,
        created_by=user.id,
    )
    db.session.add(policy)
    db.session.flush()
    return policy, True


def activate_cycle_policy(user, policy):
    _authorize_admin(user)
    active = current_cycle_policy(required=False, lock=True)
    if active and active.id != policy.id:
        raise CycleUseCaseError(
            "已有活动推免周期；请使用显式周期切换", code="active_cycle_exists"
        )
    if policy.status == "retired":
        raise CycleUseCaseError("已退役政策不能重新启用")
    settings = _settings_for_update()
    policy.status = "active"
    policy.active_marker = 1
    policy.activated_by = user.id
    policy.activated_at = utcnow()
    settings.active_cycle_policy_id = policy.id
    settings.academic_year = str(policy.cycle_code)
    db.session.flush()
    return policy


def switch_cycle_policy(user, policy, *, expected_active_id):
    _authorize_admin(user)
    active = current_cycle_policy(required=True, lock=True)
    if active.id != expected_active_id:
        raise CycleUseCaseError("活动周期已变化", code="version_conflict")
    if active.id == policy.id:
        return active
    if policy.status == "retired":
        raise CycleUseCaseError("已退役政策不能重新启用")
    settings = _settings_for_update()
    active.status = "retired"
    active.active_marker = None
    active.retired_at = utcnow()
    policy.status = "active"
    policy.active_marker = 1
    policy.activated_by = user.id
    policy.activated_at = utcnow()
    settings.active_cycle_policy_id = policy.id
    settings.academic_year = str(policy.cycle_code)
    db.session.flush()
    return policy
