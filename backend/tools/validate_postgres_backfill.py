"""Destructive legacy repair validation for the explicitly isolated PostgreSQL DB."""
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app
from extensions import db
from legacy_models import Application
from models import Student, User
from use_cases.migration import run_legacy_backfill
from legacy_models import LegacyBackfillBatch, LegacyBackfillItem
from workflow_models import (
                             RecommendationCyclePolicy, RuleVersion, ScoreEntry,
                             StudentScoreSnapshot)


def main():
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgresql+")):
        raise SystemExit("DATABASE_URL must target isolated PostgreSQL")
    with app.app_context():
        if db.engine.dialect.name != "postgresql":
            raise SystemExit("PostgreSQL dialect required")
        batch = LegacyBackfillBatch.query.filter_by(batch_key="pg-backfill-resume").first()
        if batch:
            LegacyBackfillItem.query.filter_by(batch_id=batch.id).delete()
            db.session.delete(batch); db.session.commit()
        old = Application.query.filter(Application.project_name.like("PG回填%" )).all()
        for application in old:
            ScoreEntry.query.filter_by(source_type="legacy_application", source_id=str(application.id)).delete()
            db.session.delete(application)
        StudentScoreSnapshot.query.filter_by(student_id="PG-BF").delete()
        Student.query.filter_by(student_id="PG-BF").delete()
        db.session.commit()

        template = Student.query.filter_by(student_id="PG-S1").one()
        admin = User.query.filter_by(username="pg-backfill-admin").first()
        if admin is None:
            admin = User(username="pg-backfill-admin", name="PG回填管理员", password="test",
                         role="admin", status="active", faculty_id=template.faculty_id)
            db.session.add(admin); db.session.flush()
        policy = RecommendationCyclePolicy.query.filter_by(cycle_code=2026, version=99).first()
        if policy is None:
            policy = RecommendationCyclePolicy(
                cycle_code=2026, version=99, display_name="PG修复验证周期",
                eligible_award_start_date=date(2023, 9, 1),
                eligible_award_end_date=date(2026, 8, 31), boundary="inclusive",
                digest=RecommendationCyclePolicy.canonical_digest(
                    2026, date(2023, 9, 1), date(2026, 8, 31)),
                status="retired", created_by=admin.id,
            )
            db.session.add(policy); db.session.flush()
        student = Student(
            student_id="PG-BF", student_name="PG回填学生", faculty_id=template.faculty_id,
            department_id=template.department_id, major_id=template.major_id, academic_score=80,
        )
        db.session.add(student); db.session.flush()
        version = RuleVersion.query.filter_by(status="published").order_by(RuleVersion.id).first()
        rows = []
        for index in range(2):
            row = Application(
                student_id=student.student_id, student_name=student.student_name,
                faculty_id=student.faculty_id, department_id=student.department_id,
                major_id=student.major_id, application_type="academic",
                project_name=f"PG回填{index}", status="approved", final_score=5,
                rule_id=version.rule_id, cycle_code=2026,
                cycle_policy_version_id=policy.id,
            )
            db.session.add(row); rows.append(row)
        db.session.commit()
        mappings = [{"application_id": row.id, "rule_version_id": version.id,
                     "evidence_reference": f"pg-archive:{row.id}",
                     "confirmed_by": "pg-backfill-admin"} for row in rows]
        first = run_legacy_backfill(2026, batch_key="pg-backfill-resume",
            backup_reference="pg-backup-verified", cycle_policy_version_id=policy.id,
            mappings=mappings, max_items=1)
        if first.status != "running":
            raise AssertionError(first.status)
        resumed = run_legacy_backfill(2026, batch_key="pg-backfill-resume",
            backup_reference="pg-backup-verified", cycle_policy_version_id=policy.id,
            mappings=mappings)
        run_legacy_backfill(2026, batch_key="pg-backfill-resume",
            backup_reference="pg-backup-verified", cycle_policy_version_id=policy.id,
            mappings=mappings)
        counts = {
            "items": LegacyBackfillItem.query.filter_by(batch_id=resumed.id).count(),
            "entries": ScoreEntry.query.filter_by(student_id="PG-BF", status="active").count(),
            "snapshots": StudentScoreSnapshot.query.filter_by(
                student_id="PG-BF", year=2026, status="current").count(),
        }
        if resumed.status != "completed" or counts != {"items": 2, "entries": 2, "snapshots": 1}:
            raise AssertionError({"status": resumed.status, **counts})
        print(json.dumps({"dialect": db.engine.dialect.name,
                          "repair_resume": "ok", **counts}, sort_keys=True))


if __name__ == "__main__":
    main()
