"""审核结论的显示回归。

`services/materials/service.py::_last_review` 原先把 `action="reviewed"` 固定映射成
`"review"`。`review` 不是前端 `reviewOutcomes` 的键，所以通用审核路径上的结论一直
只显示泛泛的「教师审核意见」，学生看不出是通过还是退回（竞赛事件不受影响，因为
它们有独立的 approve / return 映射）。

改为优先读事件自带的 `details["decision"]` 之后，需要守住三件事：
1. 带 decision 的事件返回真实结论；
2. 不带 decision 的旧事件不报错（前端会退化成通用文案，不比改之前更差）；
3. 竞赛事件仍走固定映射 approve / return。
"""
from datetime import datetime

from extensions import db
from material_models import MaterialEvent, MaterialRecord
from models import Student
from services.materials.service import _last_review


def _record(status="needs_correction"):
    student = Student.query.filter_by(student_id="S1").one()
    row = MaterialRecord(
        student_id=student.student_id, faculty_id=student.faculty_id,
        category="competition", year=2028, status=status, data={}, analysis={},
    )
    db.session.add(row)
    db.session.commit()
    return row


def _event(row, action, details, actor_id):
    db.session.add(MaterialEvent(
        record_id=row.id, actor_id=actor_id, action=action,
        details=details, created_at=datetime.utcnow(),
    ))
    db.session.commit()


def test_reviewed_event_reports_its_real_decision(env):
    _, _, ids = env
    row = _record()
    _event(row, "reviewed", {"decision": "return", "comment": "材料不清晰"}, ids["admin"])

    assert _last_review(row)["decision"] == "return"
    assert _last_review(row)["comment"] == "材料不清晰"


def test_legacy_reviewed_event_without_decision_does_not_crash(env):
    """升级前写入的事件没有 decision 字段：不能抛错，前端会退化成通用文案。"""
    _, _, ids = env
    row = _record()
    _event(row, "reviewed", {"comment": "旧数据没有 decision"}, ids["admin"])

    review = _last_review(row)
    assert review["comment"] == "旧数据没有 decision"
    assert review["decision"] is None
    assert review["actor"]["name"] == "管理员"


def test_competition_events_keep_fixed_mapping(env):
    _, _, ids = env
    row = _record(status="verified")
    _event(row, "competition_approved", {}, ids["admin"])
    assert _last_review(row)["decision"] == "approve"

    row2 = _record(status="needs_correction")
    _event(row2, "competition_returned", {}, ids["admin"])
    assert _last_review(row2)["decision"] == "return"


def test_latest_event_wins(env):
    _, _, ids = env
    row = _record()
    _event(row, "reviewed", {"decision": "return", "comment": "第一次退回"}, ids["admin"])
    _event(row, "reviewed", {"decision": "approve", "comment": "补正后通过"}, ids["admin"])

    review = _last_review(row)
    assert review["decision"] == "approve"
    assert review["comment"] == "补正后通过"
