from decimal import Decimal

from extensions import db
from datetime import datetime, timedelta

from conftest import login
from models import Rule, Student
from use_cases.scoring import recalculate_score_snapshots
from workflow_models import (RankingBatch, RuleVersion, ScoreEntry,
                             ScoreRecalculationCommand, StudentScoreSnapshot)


def _seed(env):
    student = Student.query.filter_by(student_id="S1").one()
    rule = Rule(name="竞赛", type="academic", sub_type="competition", score=5)
    db.session.add(rule)
    db.session.flush()
    data = {"score": 5, "max_count": 1}
    version = RuleVersion(
        rule_id=rule.id,
        version=1,
        status="published",
        snapshot=data,
        digest=RuleVersion.canonical_digest(data),
    )
    db.session.add(version)
    db.session.flush()
    db.session.add(
        ScoreEntry(
            student_id=student.student_id,
            faculty_id=student.faculty_id,
            year=2026,
            score_group="academic",
            category="competition",
            source_type="material",
            source_id="1",
            source_revision=1,
            rule_version_id=version.id,
            raw_score=Decimal("5"),
            adjusted_score=Decimal("5"),
            effective_score=Decimal("5"),
            included=True,
            status="active",
            idempotency_key="recalc-entry",
        )
    )
    db.session.commit()
    return student, version


def test_preview_does_not_persist_and_apply_is_idempotent(env):
    student, version = _seed(env)
    preview = recalculate_score_snapshots(
        2026,
        faculty_id=student.faculty_id,
        rule_version_id=version.id,
        preview=True,
    )
    assert preview["complete"] and preview["results"][0]["preview"]
    assert StudentScoreSnapshot.query.count() == 0

    first = recalculate_score_snapshots(2026, student_id="S1")
    db.session.commit()
    second = recalculate_score_snapshots(2026, student_id="S1")
    db.session.commit()
    assert first["results"][0]["created"] is True
    assert second["results"][0]["created"] is False
    assert first["results"][0]["input_digest"] == second["results"][0]["input_digest"]
    assert StudentScoreSnapshot.query.count() == 1


def test_recalculation_reports_a_broken_student_without_claiming_complete(env):
    student, _version = _seed(env)
    entry = ScoreEntry.query.one()
    entry.rule_version_id = 999999
    db.session.commit()
    result = recalculate_score_snapshots(2026, student_id=student.student_id, preview=True)
    assert result["complete"] is False
    assert result["results"] == []
    assert result["errors"][0]["student_id"] == "S1"


def test_controlled_preview_summarizes_changes_and_draft_rankings_without_writes(env):
    student, _version = _seed(env)
    batch = RankingBatch(
        year=2026, faculty_id=student.faculty_id, major_id=student.major_id,
        scope_type="major", scope_definition={"major_id": student.major_id},
        cutoff_at=datetime(2026, 6, 1), rule_version_ids=[], status="draft",
        version=1, input_digest="ranking-before-preview", created_by=env[2]["admin"],
    )
    db.session.add(batch)
    db.session.commit()
    before_students = (student.academic_specialty_total, student.comprehensive_score)

    login(env[1], env[2]["admin"])
    response = env[1].post("/api/workflow/scores/recalculation-previews", json={
        "year": 2026, "faculty_id": student.faculty_id, "major_id": student.major_id,
    })

    assert response.status_code == 200
    body = response.get_json()
    assert body["input_summary"] == {
        "student_count": 1, "successful_count": 1, "failed_count": 0,
        "current_snapshot_count": 0,
    }
    assert body["expected_changes"]["changed_student_ids"] == ["S1"]
    assert body["results"][0]["change_type"] == "create"
    assert body["affected_draft_rankings"][0]["batch_id"] == batch.id
    assert len(body["preview_digest"]) == 64
    assert StudentScoreSnapshot.query.count() == 0
    assert RankingBatch.query.get(batch.id).status == "draft"
    assert (student.academic_specialty_total, student.comprehensive_score) == before_students


def test_controlled_preview_rejects_other_faculty_scope(env):
    _seed(env)
    login(env[1], env[2]["admin"])
    response = env[1].post("/api/workflow/scores/recalculation-previews", json={
        "year": 2026, "faculty_id": 999999,
    })
    assert response.status_code == 403
    assert StudentScoreSnapshot.query.count() == 0


def test_execute_requires_current_preview_stales_draft_and_replays(env):
    student, _version = _seed(env)
    batch = RankingBatch(
        year=2026, faculty_id=student.faculty_id, major_id=student.major_id,
        scope_type="major", scope_definition={"major_id": student.major_id},
        cutoff_at=datetime(2026, 6, 1), rule_version_ids=[], status="draft",
        version=1, input_digest="ranking-before-execute", created_by=env[2]["admin"])
    db.session.add(batch); db.session.commit()
    login(env[1], env[2]["admin"])
    preview = env[1].post("/api/workflow/scores/recalculation-previews", json={
        "year": 2026, "faculty_id": student.faculty_id, "major_id": student.major_id,
    }).get_json()
    command = {"scope": preview["scope"], "preview_digest": preview["preview_digest"],
               "preview_expires_at": preview["preview_expires_at"],
               "idempotency_key": "score-recalc-2026-major"}
    first = env[1].post("/api/workflow/scores/recalculation-executions", json=command)
    second = env[1].post("/api/workflow/scores/recalculation-executions", json=command)
    assert first.status_code == 200 and first.get_json()["complete"] is True
    assert first.get_json()["stale_ranking_batch_ids"] == [batch.id]
    assert second.status_code == 200 and second.get_json()["replayed"] is True
    assert StudentScoreSnapshot.query.count() == 1
    assert ScoreRecalculationCommand.query.count() == 1
    assert db.session.get(RankingBatch, batch.id).status == "stale"


def test_execute_rejects_expired_or_stale_preview_without_writes(env):
    student, _version = _seed(env)
    login(env[1], env[2]["admin"])
    preview = env[1].post("/api/workflow/scores/recalculation-previews", json={
        "year": 2026, "faculty_id": student.faculty_id,
    }).get_json()
    expired = {"scope": preview["scope"], "preview_digest": preview["preview_digest"],
        "preview_expires_at": (datetime.utcnow() - timedelta(minutes=1)).isoformat() + "Z",
        "idempotency_key": "expired-score-recalc"}
    response = env[1].post("/api/workflow/scores/recalculation-executions", json=expired)
    assert response.status_code == 409
    stale = dict(expired, preview_expires_at=preview["preview_expires_at"],
                 preview_digest="0" * 64, idempotency_key="stale-score-recalc")
    response = env[1].post("/api/workflow/scores/recalculation-executions", json=stale)
    assert response.status_code == 409
    assert StudentScoreSnapshot.query.count() == 0
    assert ScoreRecalculationCommand.query.count() == 0


def test_execute_rolls_back_whole_scope_and_records_partial_failure(env, monkeypatch):
    student, _version = _seed(env)
    second = Student(student_id="S2", student_name="李四", faculty_id=student.faculty_id,
        department_id=student.department_id, major_id=student.major_id, academic_score=82)
    db.session.add(second); db.session.commit()
    login(env[1], env[2]["admin"])
    preview = env[1].post("/api/workflow/scores/recalculation-previews", json={
        "year": 2026, "faculty_id": student.faculty_id, "major_id": student.major_id,
    }).get_json()
    import use_cases.scoring as scoring
    original = scoring.rebuild_student_snapshot
    calls = {"count": 0}
    def fail_second(student_id, year):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("injected rebuild failure")
        return original(student_id, year)
    monkeypatch.setattr(scoring, "rebuild_student_snapshot", fail_second)
    response = env[1].post("/api/workflow/scores/recalculation-executions", json={
        "scope": preview["scope"], "preview_digest": preview["preview_digest"],
        "preview_expires_at": preview["preview_expires_at"],
        "idempotency_key": "partial-failure-score-recalc",
    })
    body = response.get_json()
    assert response.status_code == 409 and body["complete"] is False
    assert body["status"] == "failed"
    assert body["objects"][0]["status"] == "rolled_back"
    assert body["failed_objects"][0]["student_id"] == "S2"
    assert StudentScoreSnapshot.query.count() == 0
    assert ScoreRecalculationCommand.query.one().status == "failed"



def test_material_cap_keeps_candidates_across_review_rebuild_and_replacement(env, active_cycle):
    from material_models import MaterialRecord
    from models import User
    from use_cases.rule_versions import publish_rule_version
    from use_cases.scoring import explain_student_score, rebuild_student_snapshot, score_verified_material

    actor = db.session.get(User, env[2]["admin"])
    rule = Rule(name="累计限额测试", type="academic", sub_type="honor", score=6,
                faculty_id=actor.faculty_id, max_count=2, total_score_cap=8, status="active")
    db.session.add(rule)
    version, _ = publish_rule_version(rule, published_by=actor, cycle_code=active_cycle.cycle_code)
    for value in (4, 5, 6):
        row = MaterialRecord(student_id="S1", faculty_id=actor.faculty_id, category="honor",
                             year=active_cycle.cycle_code, data={}, analysis={}, status="scored",
                             rule_version_id=version.id, cycle_policy_version_id=active_cycle.id)
        db.session.add(row)
        db.session.flush()
        score_verified_material(row, str(value), actor=actor, override_score=value, override_reason="测试核验")
    entries = ScoreEntry.query.order_by(ScoreEntry.id).all()
    assert [entry.candidate_score for entry in entries] == [4, 5, 6]
    assert [entry.effective_score for entry in entries] == [0, 2, 6]
    snapshot, created = rebuild_student_snapshot("S1", active_cycle.cycle_code)
    assert not created and snapshot.specialty_raw_score == 8
    details = explain_student_score("S1", active_cycle.cycle_code)["entries"]
    assert sum(Decimal(item["included_score"]) for item in details) == 8
    entries[-1].status, entries[-1].included = "invalidated", False
    snapshot, _ = rebuild_student_snapshot("S1", active_cycle.cycle_code)
    assert [entry.effective_score for entry in entries[:2]] == [3, 5]
    assert snapshot.specialty_raw_score == 8
