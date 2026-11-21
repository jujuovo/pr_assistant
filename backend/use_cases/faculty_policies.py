from sqlalchemy import update

from extensions import db
from models import Faculty
from workflow_models import FacultyScoringPolicy
from use_cases.structured_rules import StructuredRuleError


def policies(user):
    if not user or user.role != "admin" or not user.faculty_id:
        raise StructuredRuleError("需要本学院管理员权限", status_code=403)
    return FacultyScoringPolicy.query.filter_by(faculty_id=user.faculty_id)


def serialize(row):
    return {key: getattr(row, key) for key in
            ("id", "cycle_code", "title", "status", "revision", "source_id", "sections")}


def save_draft(user, data, policy_id=None):
    query = policies(user)
    if not isinstance(data, dict):
        raise StructuredRuleError("请提供草稿内容")
    title, cycle = data.get("title"), data.get("cycle_code")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 120:
        raise StructuredRuleError("名称须为 1 至 120 个字符")
    if type(cycle) is not int or not 2000 <= cycle <= 2100:
        raise StructuredRuleError("请填写有效推免年份")
    sections = data.get("sections")
    if not isinstance(sections, dict):
        raise StructuredRuleError("章节配置须为 JSON 对象")
    values = dict(title=title.strip(), cycle_code=cycle, sections=sections)
    if policy_id is None:
        source_id = data.get("source_id")
        if source_id is not None and (type(source_id) is not int or
                                      not query.filter_by(id=source_id).first()):
            raise StructuredRuleError("来源规则不存在", status_code=404)
        row = FacultyScoringPolicy(faculty_id=user.faculty_id, source_id=source_id, **values)
        db.session.add(row)
    else:
        revision = data.get("revision")
        if type(revision) is not int or revision < 1:
            raise StructuredRuleError("缺少草稿修订号")
        row = query.filter_by(id=policy_id).first()
        if row is None:
            raise StructuredRuleError("草稿不存在", status_code=404)
        changed = query.filter_by(id=policy_id, revision=revision, status="draft").update(
            dict(**values, revision=revision + 1), synchronize_session=False)
        if not changed:
            raise StructuredRuleError("草稿版本已变化或已经发布，请重新打开", status_code=409)
    db.session.commit()
    db.session.refresh(row)
    return serialize(row)


def delete_policy(user, policy_id):
    query = policies(user).filter_by(id=policy_id)
    changed = query.filter(FacultyScoringPolicy.status.in_(("draft", "retired"))).update(
        {"status": "deleted", "revision": FacultyScoringPolicy.revision + 1},
        synchronize_session=False,
    )
    if not changed:
        row = query.first()
        if row is None:
            raise StructuredRuleError("规则不存在", status_code=404)
        if row.status != "deleted":
            raise StructuredRuleError("请先发布本学院、本届的替代版本，再删除当前正式版", status_code=409)
    db.session.commit()



def current_policy(faculty_id, cycle_code):
    return FacultyScoringPolicy.query.filter_by(
        faculty_id=faculty_id, cycle_code=cycle_code, status="published"
    ).one_or_none()



def lock_faculty_scoring(faculty_id):
    """Serialize policy publication and material review before acquiring student locks."""
    faculty = Faculty.__table__
    if db.session.get_bind().dialect.name == "sqlite":
        # SQLite ignores FOR UPDATE. Acquire its writer lock without changing faculty data.
        db.session.execute(update(faculty).where(faculty.c.id == faculty_id).values(
            id=faculty.c.id, updated_at=faculty.c.updated_at,
        ))
    else:
        Faculty.query.with_entities(Faculty.id).filter_by(id=faculty_id).with_for_update().one()
