import pytest
from extensions import db
from models import User
from use_cases.faculty_policies import policies, save_draft
from use_cases.structured_rules import StructuredRuleError
from workflow_models import FacultyScoringPolicy


def test_draft_lifecycle(env):
    admin = db.session.get(User, env[2]["admin"])
    data = dict(title="学院规则", cycle_code=2028, sections={"志愿服务": {}})
    original = save_draft(admin, data)
    updated = save_draft(admin, dict(data, revision=1, sections={"竞赛": {"限项": 2}}), original["id"])
    assert updated["revision"] == 2
    with pytest.raises(StructuredRuleError) as conflict:
        save_draft(admin, dict(data, revision=1), original["id"])
    assert conflict.value.status_code == 409
    row = db.session.get(FacultyScoringPolicy, original["id"])
    row.status = "published"
    db.session.commit()
    with pytest.raises(StructuredRuleError):
        save_draft(admin, dict(data, revision=2), row.id)
    for cycle in (2028, 2029):
        copied = save_draft(admin, dict(updated, cycle_code=cycle, source_id=row.id))
        assert copied["status"] == "draft" and copied["source_id"] == row.id
    other = db.session.get(User, env[2]["other"])
    other.role = "admin"
    assert policies(other).count() == 0
    with pytest.raises(StructuredRuleError):
        save_draft(other, dict(data, source_id=row.id))


def test_delete_protects_current_version_and_keeps_retired_history(env):
    from use_cases.faculty_policies import delete_policy

    admin = db.session.get(User, env[2]["admin"])
    data = dict(title="删除测试", cycle_code=2028, sections={})
    draft = save_draft(admin, data)
    official = save_draft(admin, data)
    row = db.session.get(FacultyScoringPolicy, official["id"])
    row.status = "published"
    db.session.commit()
    with pytest.raises(StructuredRuleError) as error:
        delete_policy(admin, row.id)
    assert error.value.status_code == 409
    delete_policy(admin, draft["id"])
    row.status = "retired"
    db.session.commit()
    delete_policy(admin, row.id)
    assert db.session.get(FacultyScoringPolicy, row.id).status == "deleted"
    assert db.session.get(FacultyScoringPolicy, draft["id"]).status == "deleted"


def test_publish_scope_and_rollback(env):
    from use_cases.faculty_policy_publication import preview_publication, publish_policy

    admin = db.session.get(User, env[2]["admin"])
    other = db.session.get(User, env[2]["other"])
    other.role = "admin"
    data = dict(title="发布测试", cycle_code=2028, sections={"学业成绩计算": {"academic_score_weight": 80}})
    first = save_draft(admin, data)
    other_draft = save_draft(other, data)
    next_cycle = save_draft(admin, dict(data, cycle_code=2029))

    def publish(user, row):
        preview = preview_publication(user, row["id"])
        publish_policy(user, row["id"], preview["digest"], apply_scoring=lambda _: None)

    publish(admin, first)
    publish(admin, next_cycle)
    publish(other, other_draft)
    draft = save_draft(admin, data)
    preview = preview_publication(admin, draft["id"])
    updated = save_draft(admin, dict(data, revision=1, title="已修改"), draft["id"])
    with pytest.raises(StructuredRuleError, match="重新预览"):
        publish_policy(admin, draft["id"], preview["digest"], apply_scoring=lambda _: None)

    def fail(_):
        raise RuntimeError("重算失败")

    preview = preview_publication(admin, updated["id"])
    with pytest.raises(RuntimeError, match="重算失败"):
        publish_policy(admin, draft["id"], preview["digest"], apply_scoring=fail)
    db.session.expire_all()
    assert db.session.get(FacultyScoringPolicy, first["id"]).status == "published"
    assert db.session.get(FacultyScoringPolicy, draft["id"]).status == "draft"
    publish(admin, draft)
    assert db.session.get(FacultyScoringPolicy, first["id"]).status == "retired"
    assert db.session.get(FacultyScoringPolicy, draft["id"]).status == "published"
    assert db.session.get(FacultyScoringPolicy, next_cycle["id"]).status == "published"
    assert db.session.get(FacultyScoringPolicy, other_draft["id"]).status == "published"


def test_published_totals_rebuild_existing_snapshot(env):
    from use_cases.faculty_policy_publication import (
        preview_supported_publication, publish_supported_policy,
    )
    from use_cases.scoring import rebuild_student_snapshot
    from workflow_models import StudentScoreSnapshot

    admin = db.session.get(User, env[2]["admin"])
    before, _ = rebuild_student_snapshot("S1", 2028)
    db.session.commit()
    row = save_draft(admin, {
        "title": "重算权重", "cycle_code": 2028,
        "sections": {
            "学业成绩计算": {"academic_score_weight": 75},
            "学术专长封顶": {"specialty_max_score": 15},
            "综合表现封顶": {"performance_max_score": 5},
            "学科竞赛": {"competition_max_count": 3},
        },
    })
    preview = preview_supported_publication(admin, row["id"])
    assert preview["score_changes"] == [{"student_id": "S1", "before": "64.0000", "after": "60.0000"}]
    assert StudentScoreSnapshot.query.count() == 1
    assert db.session.get(FacultyScoringPolicy, row["id"]).status == "draft"
    publish_supported_policy(admin, row["id"], preview)
    current = StudentScoreSnapshot.query.filter_by(student_id="S1", year=2028, status="current").one()
    assert current.academic_weight == 75
    assert current.comprehensive_score == current.academic_base_score * 75 / 100
    assert db.session.get(StudentScoreSnapshot, before.id).status == "superseded"


def test_review_lock_waits_for_publication_commit(tmp_path):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError
    from threading import Event

    from flask import Flask
    from models import Faculty
    from use_cases.faculty_policies import current_policy, lock_faculty_scoring

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + str(tmp_path / "publication.db")
    db.init_app(app)
    with app.app_context():
        db.create_all()
        faculty = Faculty(name="并发测试学院")
        db.session.add(faculty)
        db.session.commit()
        faculty_id = faculty.id
        lock_faculty_scoring(faculty_id)
        db.session.add(FacultyScoringPolicy(
            faculty_id=faculty_id, cycle_code=2028, title="新版本",
            status="published", sections={},
        ))
        db.session.flush()
        waiting = Event()

        def read_policy_as_reviewer():
            with app.app_context():
                waiting.set()
                lock_faculty_scoring(faculty_id)
                return current_policy(faculty_id, 2028).title

        with ThreadPoolExecutor(max_workers=1) as pool:
            review = pool.submit(read_policy_as_reviewer)
            try:
                assert waiting.wait(2)
                with pytest.raises(TimeoutError):
                    review.result(timeout=0.1)
            finally:
                db.session.commit()
            assert review.result(timeout=5) == "新版本"
