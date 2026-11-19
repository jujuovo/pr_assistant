"""Destructive validation for an explicitly isolated PostgreSQL database."""

import json
import os
import threading

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError


def main():
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgresql+")):
        raise SystemExit("DATABASE_URL must target isolated PostgreSQL")
    engine = create_engine(url)
    if engine.dialect.name != "postgresql":
        raise SystemExit("PostgreSQL dialect required")
    report = {"dialect": engine.dialect.name}
    inspector = inspect(engine)
    expected = {"rule_version", "score_entry", "student_score_snapshot",
                "ranking_batch", "ranking_entry", "material_review_command",
                "ranking_export_audit", "legacy_backfill_batch", "legacy_backfill_item",
                "recommendation_cycle_policy", "review_scoring_command",
                "score_override_audit", "structured_material_migration_batch",
                "structured_material_migration_item"}
    missing = sorted(expected - set(inspector.get_table_names()))
    if missing:
        raise AssertionError(f"migration tables missing: {missing}")
    report["migration_tables"] = "ok"

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM ranking_export_audit"))
        conn.execute(text("DELETE FROM ranking_entry"))
        conn.execute(text("DELETE FROM ranking_batch"))
        conn.execute(text("DELETE FROM score_override_audit"))
        conn.execute(text("DELETE FROM review_scoring_command"))
        conn.execute(text("DELETE FROM material_review_command"))
        conn.execute(text("DELETE FROM structured_material_migration_item"))
        conn.execute(text("DELETE FROM structured_material_migration_batch"))
        conn.execute(text("DELETE FROM legacy_backfill_item"))
        conn.execute(text("DELETE FROM legacy_backfill_batch"))
        conn.execute(text("DELETE FROM student_score_snapshot"))
        conn.execute(text("DELETE FROM score_entry"))
        conn.execute(text("DELETE FROM rule_version"))
        conn.execute(text("DELETE FROM material_event"))
        conn.execute(text("DELETE FROM material_attachment"))
        conn.execute(text("DELETE FROM material_record"))
        conn.execute(text("DELETE FROM application"))
        conn.execute(text("UPDATE system_settings SET active_cycle_policy_id=NULL"))
        conn.execute(text("DELETE FROM recommendation_cycle_policy"))
        conn.execute(text("DELETE FROM \"user\""))
        conn.execute(text("DELETE FROM student"))
        conn.execute(text("DELETE FROM rule"))
        conn.execute(text("DELETE FROM major"))
        conn.execute(text("DELETE FROM department"))
        conn.execute(text("DELETE FROM faculty"))
        faculty = conn.execute(text("INSERT INTO faculty(name) VALUES ('PG验证学院') RETURNING id")).scalar_one()
        department = conn.execute(text("INSERT INTO department(name,faculty_id) VALUES ('PG验证系',:f) RETURNING id"), {"f": faculty}).scalar_one()
        major = conn.execute(text("INSERT INTO major(name,department_id) VALUES ('PG验证专业',:d) RETURNING id"), {"d": department}).scalar_one()
        conn.execute(text("INSERT INTO student(student_id,student_name,faculty_id,department_id,major_id,academic_score) VALUES ('PG-S1','验证学生',:f,:d,:m,80)"), {"f": faculty, "d": department, "m": major})
        rule = conn.execute(text("INSERT INTO rule(name,type,sub_type,score,status,faculty_id) VALUES ('PG规则','academic','competition',5,'active',:f) RETURNING id"), {"f": faculty}).scalar_one()
        version = conn.execute(text("INSERT INTO rule_version(rule_id,version,status,snapshot,digest,published_at,created_at) VALUES (:r,1,'published',CAST(:s AS json),'pg-digest',now(),now()) RETURNING id"), {"r": rule, "s": json.dumps({"score": 5})}).scalar_one()
        material = conn.execute(text("INSERT INTO material_record(student_id,faculty_id,category,year,status,data,analysis,version,created_at,updated_at) VALUES ('PG-S1',:f,'competition',2026,'submitted',CAST('{}' AS json),CAST('{}' AS json),1,now(),now()) RETURNING id"), {"f": faculty}).scalar_one()
        available_material = conn.execute(text("INSERT INTO material_record(student_id,faculty_id,category,year,status,data,analysis,version,created_at,updated_at) VALUES ('PG-S1',:f,'competition',2026,'rule_available',CAST('{}' AS json),CAST('{}' AS json),1,now(),now()) RETURNING id"), {"f": faculty}).scalar_one()
        rollback_material = conn.execute(text("INSERT INTO material_record(student_id,faculty_id,category,year,status,data,analysis,version,created_at,updated_at) VALUES ('PG-S1',:f,'competition',2026,'submitted',CAST('{}' AS json),CAST('{}' AS json),1,now(),now()) RETURNING id"), {"f": faculty}).scalar_one()
        params = {"student": "PG-S1", "faculty": faculty, "rule_version": version,
                  "material": material}
        statement = text("""INSERT INTO score_entry
            (student_id,faculty_id,year,score_group,category,source_type,source_id,
             source_revision,material_record_id,rule_version_id,raw_score,adjusted_score,
             effective_score,included,status,idempotency_key,created_at,updated_at)
            VALUES (:student,:faculty,2026,'academic','competition','material',CAST(:material AS text),
             1,:material,:rule_version,5,5,5,true,'active','pg-unique-key',now(),now())""")
        conn.execute(statement, params)
    try:
        with engine.begin() as conn:
            conn.execute(statement, params)
    except IntegrityError:
        report["unique_constraint"] = "ok"
    else:
        raise AssertionError("duplicate score entry was accepted")

    barrier = threading.Barrier(2)
    cas_results = []
    def cas_review(decision):
        with engine.begin() as conn:
            barrier.wait()
            result = conn.execute(text("UPDATE material_record SET status=:decision,version=version+1 WHERE id=:id AND status='submitted' AND version=1"), {"decision": decision, "id": material})
            cas_results.append(result.rowcount)
    threads = [threading.Thread(target=cas_review, args=(value,)) for value in ("verified", "rejected")]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    if sorted(cas_results) != [0, 1]:
        raise AssertionError(f"concurrent CAS results: {cas_results}")
    report["concurrent_review_cas"] = "ok"

    barrier = threading.Barrier(2)
    submit_results = []
    def cas_resubmit():
        with engine.begin() as conn:
            barrier.wait()
            result = conn.execute(text("""UPDATE material_record
                SET status='submitted',rule_version_id=:rule_version,version=version+1
                WHERE id=:id AND status='rule_available' AND version=1"""),
                {"rule_version": version, "id": available_material})
            submit_results.append(result.rowcount)
    threads = [threading.Thread(target=cas_resubmit) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    if sorted(submit_results) != [0, 1]:
        raise AssertionError(f"concurrent resubmit CAS results: {submit_results}")
    report["concurrent_resubmit_cas"] = "ok"

    rollback_params = dict(params, material=rollback_material)
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE material_record SET status='scored' WHERE id=:id"),
                         {"id": rollback_material})
            conn.execute(statement, rollback_params)
    except IntegrityError:
        with engine.connect() as conn:
            status = conn.execute(text("SELECT status FROM material_record WHERE id=:id"),
                                  {"id": rollback_material}).scalar_one()
        if status != "submitted":
            raise AssertionError(f"review rollback left status {status}")
        report["review_transaction_rollback"] = "ok"
    else:
        raise AssertionError("injected duplicate did not roll back review transaction")

    locked = threading.Event()
    release = threading.Event()
    lock_result = []
    def holder():
        with engine.begin() as conn:
            conn.execute(text("SELECT student_id FROM student WHERE student_id='PG-S1' FOR UPDATE"))
            locked.set(); release.wait(5)
    def contender():
        locked.wait(5)
        try:
            with engine.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout='500ms'"))
                conn.execute(text("SELECT student_id FROM student WHERE student_id='PG-S1' FOR UPDATE"))
        except DBAPIError:
            lock_result.append("blocked")
        finally:
            release.set()
    first, second = threading.Thread(target=holder), threading.Thread(target=contender)
    first.start(); second.start(); first.join(); second.join()
    if lock_result != ["blocked"]:
        raise AssertionError(f"row lock was not enforced: {lock_result}")
    report["row_lock"] = "ok"
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
