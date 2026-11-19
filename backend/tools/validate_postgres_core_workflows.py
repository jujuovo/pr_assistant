"""Validate change 8.6 against an explicitly isolated PostgreSQL database."""

import json
import os
import sys
import threading
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app import app
from extensions import db
from models import Department, Faculty, Major, Rule, Student, User
from use_cases.scoring import recalculate_score_snapshots
from workflow_models import (
    CompetitionRulePackage,
    RankingBatch,
    RankingCommand,
    RuleVersion,
    ScoreEntry,
    StudentScoreSnapshot,
)


YEAR = 2098


def _require_isolated_postgres():
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgresql+")):
        raise SystemExit("DATABASE_URL must target an isolated PostgreSQL database")
    if db.engine.dialect.name != "postgresql":
        raise SystemExit("PostgreSQL dialect required")
    database = db.session.execute(text("select current_database()")) .scalar_one()
    if database != "gradpush_openspec":
        raise SystemExit(f"refusing non-validation database: {database}")


def _seed():
    suffix = uuid.uuid4().hex[:8]
    faculty = Faculty(name=f"PG8.6学院-{suffix}")
    db.session.add(faculty)
    db.session.flush()
    department = Department(name=f"PG8.6系-{suffix}", faculty_id=faculty.id)
    db.session.add(department)
    db.session.flush()
    major = Major(name=f"PG8.6专业-{suffix}", department_id=department.id)
    db.session.add(major)
    db.session.flush()
    admin = User(
        username=f"pg86-admin-{suffix}", password="validation-only", name="PG验证管理员",
        role="admin", status="active", faculty_id=faculty.id,
    )
    db.session.add(admin)
    for number in (1, 2):
        db.session.add(Student(
            student_id=f"PG86-{suffix}-{number}", student_name=f"PG验证学生{number}",
            faculty_id=faculty.id, department_id=department.id, major_id=major.id,
            academic_score=80 + number,
        ))
    db.session.flush()
    rule = Rule(
        name=f"PG8.6规则-{suffix}", type="academic", sub_type="research",
        score=5, status="active", faculty_id=faculty.id,
    )
    db.session.add(rule)
    db.session.flush()
    snapshot = {"score": 5, "max_count": None}
    version = RuleVersion(
        rule_id=rule.id, version=1, status="published", snapshot=snapshot,
        digest=RuleVersion.canonical_digest(snapshot), published_by=admin.id,
    )
    db.session.add(version)
    db.session.flush()
    students = Student.query.filter(Student.student_id.like(f"PG86-{suffix}-%")).all()
    for student in students:
        db.session.add(ScoreEntry(
            student_id=student.student_id, faculty_id=faculty.id, year=YEAR,
            score_group="academic", category="research", source_type="validation",
            source_id=student.student_id, source_revision=1, rule_version_id=version.id,
            raw_score=Decimal("5"), adjusted_score=Decimal("5"),
            effective_score=Decimal("5"), included=True, status="active",
            idempotency_key=f"pg86-score-{suffix}-{student.student_id}",
        ))
    package_snapshot = {"package_id": f"pg86-{suffix}", "catalog": []}
    package = CompetitionRulePackage(
        package_id=f"pg86-{suffix}", cycle_code=YEAR, scope_key=suffix, version=1,
        status="current", snapshot=package_snapshot,
        digest=CompetitionRulePackage.canonical_digest(package_snapshot),
        current_scope_key=CompetitionRulePackage.current_key(YEAR, suffix),
        created_by=admin.id, published_by=admin.id,
    )
    batch = RankingBatch(
        year=YEAR, faculty_id=faculty.id, major_id=major.id, scope_type="major",
        scope_definition={"major_id": major.id}, cutoff_at=datetime(YEAR, 6, 1),
        rule_version_ids=[version.id], score_precision=4, status="draft", version=1,
        input_digest=f"pg86-ranking-{suffix}", created_by=admin.id,
    )
    db.session.add_all([package, batch])
    db.session.commit()
    return suffix, faculty, major, admin, version, package, batch, students


def _validate_unique_current(package, admin):
    duplicate_snapshot = {"package_id": f"{package.package_id}-duplicate", "catalog": []}
    duplicate = CompetitionRulePackage(
        package_id=duplicate_snapshot["package_id"], cycle_code=package.cycle_code,
        scope_key=package.scope_key, version=2, status="current",
        snapshot=duplicate_snapshot,
        digest=CompetitionRulePackage.canonical_digest(duplicate_snapshot),
        current_scope_key=package.current_scope_key, created_by=admin.id,
        published_by=admin.id,
    )
    db.session.add(duplicate)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    else:
        raise AssertionError("a second current rule package was accepted")


def _validate_ranking_cas_and_lock(batch_id):
    engine = db.engine
    barrier = threading.Barrier(2)
    cas_results = []

    def cas(target):
        with engine.begin() as connection:
            barrier.wait()
            result = connection.execute(text(
                "update ranking_batch set status=:target, version=version+1 "
                "where id=:id and status='draft' and version=1"
            ), {"target": target, "id": batch_id})
            cas_results.append(result.rowcount)

    threads = [threading.Thread(target=cas, args=(value,))
               for value in ("frozen", "stale")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if sorted(cas_results) != [0, 1]:
        raise AssertionError(f"ranking CAS results: {cas_results}")

    locked = threading.Event()
    release = threading.Event()
    lock_results = []

    def holder():
        with engine.begin() as connection:
            connection.execute(text(
                "select id from ranking_batch where id=:id for update"
            ), {"id": batch_id})
            locked.set()
            release.wait(5)

    def contender():
        locked.wait(5)
        try:
            with engine.begin() as connection:
                connection.execute(text("set local lock_timeout='500ms'"))
                connection.execute(text(
                    "select id from ranking_batch where id=:id for update"
                ), {"id": batch_id})
        except DBAPIError:
            lock_results.append("blocked")
        finally:
            release.set()

    threads = [threading.Thread(target=holder), threading.Thread(target=contender)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    if lock_results != ["blocked"]:
        raise AssertionError(f"ranking row lock result: {lock_results}")


def _validate_batch_recalculation(faculty_id, student_ids):
    result = recalculate_score_snapshots(YEAR, faculty_id=faculty_id)
    if not result["complete"] or {item["student_id"] for item in result["results"]} != set(student_ids):
        raise AssertionError(result)
    db.session.commit()
    count = StudentScoreSnapshot.query.filter(
        StudentScoreSnapshot.student_id.in_(student_ids),
        StudentScoreSnapshot.year == YEAR,
        StudentScoreSnapshot.status == "current",
    ).count()
    if count != 2:
        raise AssertionError(f"expected two current snapshots, got {count}")


def _validate_transaction_rollback(batch_id, admin_id):
    command = RankingCommand(
        idempotency_key=f"pg86-rollback-{batch_id}", action="freeze",
        request_digest="a" * 64, batch_id=batch_id, result={"ok": True},
        created_by=admin_id,
    )
    db.session.add(command)
    db.session.commit()
    before = db.session.get(RankingBatch, batch_id).status
    try:
        with db.engine.begin() as connection:
            connection.execute(text(
                "update ranking_batch set status='withdrawn' where id=:id"
            ), {"id": batch_id})
            connection.execute(text(
                "insert into ranking_command "
                "(idempotency_key,action,request_digest,batch_id,result,created_by,created_at) "
                "values (:key,'freeze',:digest,:batch,cast(:result as json),:actor,now())"
            ), {"key": command.idempotency_key, "digest": "b" * 64,
                "batch": batch_id, "result": json.dumps({"ok": False}),
                "actor": admin_id})
    except IntegrityError:
        pass
    else:
        raise AssertionError("duplicate command did not abort transaction")
    db.session.expire_all()
    if db.session.get(RankingBatch, batch_id).status != before:
        raise AssertionError("failed command left a partial ranking status update")


def _validate_indexes_and_plans(faculty_id, major_id):
    required = {
        "competition_rule_package": "uq_competition_package_current_scope",
        "ranking_batch": "ix_ranking_batch_workflow_scope",
        "score_entry": "ix_score_entry_recalculation_scope",
        "student_score_snapshot": "ix_score_snapshot_current_scope",
    }
    inspector = inspect(db.engine)
    for table, index_name in required.items():
        names = {item["name"] for item in inspector.get_indexes(table)}
        names.update(item["name"] for item in inspector.get_unique_constraints(table))
        if index_name not in names:
            raise AssertionError(f"missing {table}.{index_name}: {sorted(names)}")
    queries = {
        "ranking": (
            "select id from ranking_batch where year=:year and faculty_id=:faculty "
            "and major_id=:major and status='draft'",
            {"year": YEAR, "faculty": faculty_id, "major": major_id},
            "ix_ranking_batch_workflow_scope",
        ),
        "score": (
            "select student_id from score_entry where faculty_id=:faculty and year=:year "
            "and status='active' order by student_id",
            {"year": YEAR, "faculty": faculty_id},
            "ix_score_entry_recalculation_scope",
        ),
        "snapshot": (
            "select student_id from student_score_snapshot where faculty_id=:faculty "
            "and year=:year and status='current' order by student_id",
            {"year": YEAR, "faculty": faculty_id},
            "ix_score_snapshot_current_scope",
        ),
    }
    with db.engine.begin() as connection:
        connection.execute(text("set local enable_seqscan=off"))
        for label, (sql, params, expected_index) in queries.items():
            plan = "\n".join(row[0] for row in connection.execute(
                text(f"explain {sql}"), params
            ))
            if expected_index not in plan:
                raise AssertionError(f"{label} plan missed {expected_index}: {plan}")


def main():
    with app.app_context():
        _require_isolated_postgres()
        server_version = db.session.execute(text("show server_version")) .scalar_one()
        suffix, faculty, major, admin, _version, package, batch, students = _seed()
        _validate_unique_current(package, admin)
        _validate_ranking_cas_and_lock(batch.id)
        _validate_batch_recalculation(faculty.id, [student.student_id for student in students])
        _validate_transaction_rollback(batch.id, admin.id)
        _validate_indexes_and_plans(faculty.id, major.id)
        print(json.dumps({
            "database": "gradpush_openspec",
            "dialect": db.engine.dialect.name,
            "server_version": server_version,
            "validation_run": suffix,
            "unique_current_rule_package": "ok",
            "ranking_version_cas": "ok",
            "ranking_row_lock": "ok",
            "batch_score_recalculation": "ok (2 students)",
            "transaction_rollback": "ok",
            "required_index_plans": "ok",
        }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
