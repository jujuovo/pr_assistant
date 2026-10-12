"""计数式性能回归：不依赖机器快慢，验证索引结果与查询规模。"""
from collections import Counter
from contextlib import contextmanager
from decimal import Decimal
from sqlalchemy import event, inspect
import pytest
from extensions import db
from models import Application, Student
from automation_models import AutomationBatch, AutomationItem
from services import automation as rules
from services.recognition.volunteer import extract
from test_automation import credit, honor, policy, submit, view


@contextmanager
def select_queries():
    statements = []
    def track(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)
    engine = db.engine
    event.listen(engine, "before_cursor_execute", track)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", track)


def seeded_batch(kind="volunteer_credit", count=30):
    batch = AutomationBatch(student_id="S1", faculty_id=1, year=2025,
                            material_type=kind, status="completed")
    db.session.add(batch)
    db.session.flush()
    for index in range(count):
        if kind == "volunteer_credit":
            report = extract(credit(day=f"{index + 1:02d}"), 1000)
        else:
            data = honor()
            data["rec_texts"][1] = "1"
            data["rec_texts"][-1] = f"2025.12.{index + 1:02d} 活动{index}"
            report = extract(data, 1000)
        db.session.add(AutomationItem(batch_id=batch.id, filename=f"{index}.png",
                       sha256=f"{index:064x}", status="ready", report=report,
                       raw_ocr={"unused_large_blob": "x" * 10000}))
    db.session.commit()
    return batch.id


def test_transition_refresh_query_count_not_per_image(env):
    app, client, users = env
    batch_id = seeded_batch()
    db.session.expunge_all()
    batch = db.session.get(AutomationBatch, batch_id)
    with select_queries() as statements:
        rules.claim_transition(batch, batch.version, ("completed",), unsubmitted=True)
        assert len(batch.items) == 30
        assert all("raw_ocr" in inspect(item).unloaded for item in batch.items)
    # 学生锁 + 批次刷新 + 明细刷新，原来还会对每项单独 refresh。
    assert len(statements) == 3, statements


def test_preview_parses_history_once_and_does_not_fetch_raw_ocr(env, monkeypatch):
    app, client, users = env
    policy(client, users)
    current_id = seeded_batch()
    for index in range(120):
        history = AutomationBatch(student_id="S1", faculty_id=1, year=2024,
                                  material_type="volunteer_honor", status="completed")
        db.session.add(history)
        db.session.flush()
        data = honor()
        data["rec_texts"][-1] = f"2024.12.21 历史活动{index}"
        db.session.add(AutomationItem(batch_id=history.id, filename="history.png",
                      sha256=f"{index + 1000:064x}", status="ready", report=extract(data, 1000),
                      raw_ocr={"unused_large_blob": "x" * 10000}))
    db.session.commit()
    db.session.expunge_all()
    batch = db.session.get(AutomationBatch, current_id)
    list(batch.items)
    counts = Counter()
    original_dates = rules.activity_dates
    def counted_dates(item, **kwargs):
        if item.batch.material_type == "volunteer_honor":
            counts[item.id] += 1
        return original_dates(item, **kwargs)
    monkeypatch.setattr(rules, "activity_dates", counted_dates)
    with select_queries() as statements:
        result = rules.preview(batch)
    assert len(result["rows"]) == 30
    assert len(counts) == 120
    assert set(counts.values()) == {1}  # 120次，而非30*120次重复解析。
    joins = [sql for sql in statements if "FROM automation_item JOIN automation_batch ON" in " ".join(sql.split())]
    assert len(joins) == 1
    assert "raw_ocr" not in joins[0]
    assert len(statements) <= 5, statements


def reference_conflicts(item, candidates):
    """优化前的逐项扫描作为结果基线。"""
    dates, name = set(rules.activity_dates(item)), rules.activity_identity(item)
    results = []
    for other in sorted(candidates, key=lambda entry: entry.id):
        if not dates.intersection(rules.activity_dates(other)):
            continue
        other_name = rules.activity_identity(other)
        certain = bool(name and other_name and name == other_name)
        results.append({"id": other.id, "activity_dates": rules.activity_dates(other),
                        "activity_name": other_name, "status": other.status,
                        "match": "same_activity" if certain else "needs_verification",
                        "blocking": certain and (other.id < item.id or other.submitted or other.status == "approved")})
    return results


def test_date_index_matches_reference_and_deduplicates_multi_date_hits(env):
    seeded_batch(count=5)
    honor_id = seeded_batch(kind="volunteer_honor", count=5)
    credit_items = AutomationItem.query.join(AutomationBatch).filter(
        AutomationBatch.material_type == "volunteer_credit").all()
    honor_items = db.session.get(AutomationBatch, honor_id).items
    honor_items[0].activity_dates = ["2025-12-01", "2025-12-02"]
    honor_items[0].submitted = True
    credit_items[0].activity_dates = ["2025-12-01", "2025-12-02"]
    indexed = rules.DateConflictIndex(honor_items)
    for item in credit_items:
        result = rules.cross_type_conflicts(item, indexed)
        assert result == reference_conflicts(item, honor_items)
        assert len({entry["id"] for entry in result}) == len(result)


@pytest.mark.parametrize("count", [1, 30])
def test_bulk_honor_review_reads_history_constant_times(env, count):
    app, client, users = env
    policy(client, users, max_score="20")
    batch_id = seeded_batch(kind="volunteer_honor", count=count)
    submit(client, batch_id)
    from conftest import login
    login(client, users["admin"])
    report = view(client, batch_id)
    details = [{"id": row["id"], "decision": "approved", "confirmed_hours": "1"}
               for row in report["rows"]]
    db.session.expunge_all()
    with select_queries() as statements:
        result = client.post(f"/api/automation/volunteer/batches/{batch_id}/review", json={
            "version": report["version"], "status": "approved", "items": details})
    assert result.status_code == 200, result.data
    assert Decimal(result.json["final_score"]) == min(Decimal(count) / 10, Decimal(20))
    joins = [sql for sql in statements if "FROM automation_item JOIN automation_batch ON" in " ".join(sql.split())]
    # 荣誉索引 + 跨类型索引 + 返回预览的跨类型索引，不随本批行数增长。
    assert len(joins) == 3, joins
    assert all("raw_ocr" not in sql for sql in joins)


def test_honor_index_updates_manual_dates_and_excludes_self(env):
    batch_id = seeded_batch(kind="volunteer_honor", count=2)
    first, second = db.session.get(AutomationBatch, batch_id).items
    index = rules.HonorRecordIndex([first, second])
    old_key = rules.honor_event_key(first)
    assert index.find(first, event_key=old_key) is None
    assert index.find(second, event_key=old_key) == first.id
    first.activity_dates = ["2025-12-31"]
    index.update(first)
    assert index.find(second, event_key=old_key) is None
    assert index.find(second, event_key=rules.honor_event_key(first)) == first.id


def test_year_recalculation_bulk_loads_and_preserves_cap(env):
    config = {"credit_rate": "0.1", "honor_rate": "0.1", "max_score": "1", "honor_enabled": True,
              "start_date": "2025-01-01", "end_date": "2025-12-31", "rounding": "HALF_UP_4"}
    application_ids = []
    for index in range(30):
        application = Application(student_id="S1", student_name="张三", faculty_id=1,
                                  department_id=1, major_id=1, application_type="comprehensive",
                                  status="approved", final_score=0, project_name=f"活动{index}")
        db.session.add(application)
        db.session.flush()
        application_ids.append(application.id)
        batch = AutomationBatch(student_id="S1", faculty_id=1, year=2025,
                                material_type="volunteer_credit", status="approved",
                                application_id=application.id, policy_snapshot=config)
        db.session.add(batch)
        db.session.flush()
        db.session.add(AutomationItem(batch_id=batch.id, filename="test.png", sha256=f"{index:064x}",
                       status="approved", submitted=True, confirmed_hours=Decimal("5.05"),
                       raw_ocr={"unused_large_blob": "x" * 10000}))
    last_id = batch.id
    db.session.commit()
    db.session.expunge_all()
    batch = db.session.get(AutomationBatch, last_id)
    rules.lock_student("S1")
    with select_queries() as statements:
        rules.recalculate_year(batch)
    item_queries = [sql for sql in statements if "FROM automation_item" in sql]
    assert len(item_queries) == 1
    assert "raw_ocr" not in item_queries[0]
    # 一次取得关联申请 + 一次既有成绩汇总，不逐批次查询。
    assert len([sql for sql in statements if "FROM application" in sql]) == 2
    db.session.commit()
    db.session.expire_all()
    scores = [Decimal(str(db.session.get(Application, key).final_score)) for key in application_ids]
    assert scores == [Decimal("0.505"), Decimal("0.495")] + [Decimal(0)] * 28
    assert Student.query.one().comprehensive_performance_total == 1
