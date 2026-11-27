from datetime import date

import pytest

from extensions import db
from legacy_models import Application
from models import Rule, Student
from use_cases.migration import run_legacy_backfill
from legacy_models import LegacyBackfillBatch, LegacyBackfillItem
from workflow_models import (RankingBatch,
                             RuleVersion, ScoreEntry, StudentScoreSnapshot)


def _rows(policy, count=2):
    student = Student.query.filter_by(student_id="S1").one()
    rule = Rule(name="回填规则", type="academic", score=1)
    db.session.add(rule); db.session.flush()
    snap = {"score": 1, "max_count": None}
    version = RuleVersion(rule_id=rule.id, version=1, status="published",
        snapshot=snap, digest=RuleVersion.canonical_digest(snap))
    db.session.add(version); db.session.flush()
    rows = []
    for index in range(count):
        row = Application(student_id=student.student_id, student_name=student.student_name,
            faculty_id=student.faculty_id, department_id=student.department_id,
            major_id=student.major_id, application_type="academic",
            project_name=f"历史{index}", award_date=date(2026, 1, index + 1),
            status="approved", final_score=1, rule_id=rule.id, cycle_code=2026,
            cycle_policy_version_id=policy.id)
        db.session.add(row); rows.append(row)
    db.session.commit()
    return rows, version


def _mappings(rows, version):
    return [{"application_id": row.id, "rule_version_id": version.id,
             "evidence_reference": f"archive:{row.id}", "confirmed_by": "admin-test"}
            for row in rows]


def test_backfill_requires_backup_and_resumes_idempotently(env, active_cycle):
    rows, version = _rows(active_cycle); mappings = _mappings(rows, version)
    with pytest.raises(ValueError, match="backup"):
        run_legacy_backfill(2026, batch_key="b1", backup_reference="",
                            cycle_policy_version_id=active_cycle.id, mappings=mappings)
    first = run_legacy_backfill(2026, batch_key="b1", backup_reference="backup-verified",
        cycle_policy_version_id=active_cycle.id, mappings=mappings, max_items=1)
    assert first.status == "running" and ScoreEntry.query.count() == 1
    resumed = run_legacy_backfill(2026, batch_key="b1", backup_reference="backup-verified",
        cycle_policy_version_id=active_cycle.id, mappings=mappings)
    assert resumed.status == "completed" and resumed.processed_count == 2
    assert ScoreEntry.query.count() == 2 and LegacyBackfillBatch.query.count() == 1
    run_legacy_backfill(2026, batch_key="b1", backup_reference="backup-verified",
        cycle_policy_version_id=active_cycle.id, mappings=mappings)
    assert ScoreEntry.query.count() == 2 and LegacyBackfillItem.query.count() == 2
    assert StudentScoreSnapshot.query.filter_by(student_id="S1", year=2026, status="current").count() == 1


def test_backfill_isolates_one_failure(env, active_cycle, monkeypatch):
    rows, version = _rows(active_cycle); mappings = _mappings(rows, version)
    import use_cases.migration as migration
    real = migration.adapt_legacy_application
    def fail_one(application, **kwargs):
        if application.id == rows[0].id:
            raise RuntimeError("fixture failure")
        return real(application, **kwargs)
    monkeypatch.setattr(migration, "adapt_legacy_application", fail_one)
    batch = run_legacy_backfill(2026, batch_key="b2", backup_reference="backup-verified",
        cycle_policy_version_id=active_cycle.id, mappings=mappings)
    assert batch.status == "completed_with_errors" and batch.failed_count == 1
    assert ScoreEntry.query.count() == 1
    assert LegacyBackfillItem.query.filter_by(batch_id=batch.id, status="failed").count() == 1


def test_backfill_rebuilds_snapshot_and_invalidates_draft_ranking(env, active_cycle):
    rows, version = _rows(active_cycle, count=1); student = Student.query.filter_by(student_id="S1").one()
    ranking = RankingBatch(year=2026, faculty_id=student.faculty_id, major_id=student.major_id,
        scope_type="major", scope_definition={}, cutoff_at=date(2026, 12, 31),
        rule_version_ids=[], status="draft", version=1, input_digest="c"*64,
        created_by=env[2]["admin"])
    db.session.add(ranking); db.session.commit()
    run_legacy_backfill(2026, batch_key="b3", backup_reference="backup-verified",
        cycle_policy_version_id=active_cycle.id, mappings=_mappings(rows, version))
    db.session.refresh(ranking)
    assert StudentScoreSnapshot.query.filter_by(student_id="S1", year=2026, status="current").one()
    assert ranking.status == "stale" and ranking.stale_reason
