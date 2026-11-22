from conftest import login
from extensions import db
from models import Student
from workflow_models import RankingBatch,RankingEntry,RankingExportAudit
from datetime import datetime


def _batch(env):
    student=Student.query.filter_by(student_id="S1").one()
    batch=RankingBatch(year=2026,faculty_id=student.faculty_id,major_id=student.major_id,
        scope_type="major",scope_definition={"major_id":student.major_id},cutoff_at=datetime(2030,1,1),
        rule_version_ids=[],score_precision=4,status="published",version=3,input_digest="c"*64,
        created_by=env[2]["admin"],published_by=env[2]["admin"],published_at=datetime(2026,11,4))
    db.session.add(batch);db.session.flush()
    db.session.add(RankingEntry(batch_id=batch.id,student_id="S1",frozen_score=70,rank=1,
                                display_order=1,eligible=True));db.session.commit();return batch


def test_student_sees_only_personal_entry_and_export_is_audited(env):
    batch=_batch(env)
    student=Student.query.filter_by(student_id="S1").one()
    other_student=Student(student_id="S2",student_name="李四",faculty_id=student.faculty_id,
        department_id=student.department_id,major_id=student.major_id,academic_score=79)
    db.session.add(other_student);db.session.flush()
    db.session.add(RankingEntry(batch_id=batch.id,student_id="S2",frozen_score=69,rank=2,
                                display_order=2,eligible=True));db.session.commit()
    login(env[1],env[2]["student"])
    response=env[1].get(f"/api/workflow/rankings/{batch.id}")
    assert response.status_code==200 and [e["student_id"] for e in response.json["entries"]]==["S1"]
    assert response.json["total_count"]==2
    assert "score_basis" not in response.json["entries"][0]
    assert env[1].post(f"/api/workflow/rankings/{batch.id}/export",json={"purpose":"查看"}).status_code==403
    login(env[1],env[2]["admin"])
    exported=env[1].post(f"/api/workflow/rankings/{batch.id}/export",json={"purpose":"学院公示复核"})
    assert exported.status_code==200 and RankingExportAudit.query.one().entry_count==2


def test_other_faculty_cannot_read_ranking(env):
    batch=_batch(env);login(env[1],env[2]["other"])
    assert env[1].get(f"/api/workflow/rankings/{batch.id}").status_code==403


def test_ranking_options_include_only_authorized_batch_summaries(env):
    visible = _batch(env)
    hidden = RankingBatch(year=visible.year, faculty_id=visible.faculty_id,
        major_id=visible.major_id, scope_type="major", scope_definition={},
        cutoff_at=visible.cutoff_at, rule_version_ids=[], status="draft", version=1,
        input_digest="d" * 64, created_by=env[2]["admin"])
    db.session.add(hidden)
    db.session.commit()

    login(env[1], env[2]["student"])
    response = env[1].get("/api/workflow/rankings")
    assert response.status_code == 200
    assert response.json == {"items": [{
        "batch_id": visible.id, "year": 2026, "major_name": "测试专业",
        "version": 3, "status": "published",
    }]}

    login(env[1], env[2]["admin"])
    assert {item["batch_id"] for item in env[1].get("/api/workflow/rankings").json["items"]} == {
        visible.id, hidden.id,
    }

    login(env[1], env[2]["other"])
    assert env[1].get("/api/workflow/rankings").json == {"items": []}
