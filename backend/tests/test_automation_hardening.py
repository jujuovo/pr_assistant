"""状态竞态、剩余材料、逐项异常隔离、活动身份及信用15小时边界。"""
import io
import hashlib
import json
import threading
from decimal import Decimal
from unittest.mock import patch

import pytest

from conftest import env as memory_env, login
from extensions import db
from models import Application, Student
from automation_models import AutomationBatch, AutomationItem, AutomationFingerprint, AutomationReview
from blueprints import automation_bp as routes
from services.recognition.worker import run_one
from test_automation import (Provider, approve, credit, honor, image_bytes,
                             policy, submit, upload, view)


def bulk(client):
    response = client.post("/api/automation/volunteer/batches", data={
        "year": "2025", "material_type": "credit",
        "files": [(io.BytesIO(image_bytes()), "first.png"),
                  (io.BytesIO(image_bytes("gray")), "second.png")],
    })
    assert response.status_code == 202, response.data
    return response.json["id"]


class TwoCredits:
    def __init__(self, second_hours="+5.05"):
        self.count, self.second_hours = 0, second_hours

    def predict(self, path):
        self.count += 1
        return credit(day="21" if self.count == 1 else "22",
                      hours="+5.05" if self.count == 1 else self.second_hours)


@pytest.fixture
def file_env(tmp_path):
    original_init = db.init_app

    def isolated_init(app):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + (tmp_path / "concurrency.sqlite").as_posix()
        original_init(app)

    with patch.object(db, "init_app", side_effect=isolated_init):
        generator = memory_env.__wrapped__(tmp_path)
        context = next(generator)
    engine = db.engine
    try:
        yield context
    finally:
        try:
            next(generator)
        except StopIteration:
            pass
        engine.dispose()


def test_stale_retry_cannot_reset_approved_batch_or_bypass_cap(file_env, monkeypatch):
    app, client, users = file_env
    policy(client, users)
    batch = upload(client)

    class Broken:
        def predict(self, path):
            raise RuntimeError("temporary OCR failure")

    run_one(app, Broken())
    staged, resume, result = threading.Event(), threading.Event(), {}
    original_batch_at = routes.batch_at

    def paused_batch_at(batch_id):
        record = original_batch_at(batch_id)
        if threading.current_thread().name == "stale-retry":
            list(record.items)
            staged.set()
            assert resume.wait(10), "并发测试等待超时"
        return record

    monkeypatch.setattr(routes, "batch_at", paused_batch_at)

    def stale_retry():
        try:
            with app.app_context():
                stale_client = app.test_client()
                login(stale_client, users["student"])
                result["response"] = stale_client.post(f"/api/automation/volunteer/batches/{batch}/retry")
        except Exception as error:
            result["error"] = error

    thread = threading.Thread(target=stale_retry, name="stale-retry")
    thread.start()
    try:
        assert staged.wait(10)
        assert client.post(f"/api/automation/volunteer/batches/{batch}/retry").status_code == 202
        run_one(app, Provider(credit()))
        submitted = submit(client, batch)
        approved = approve(client, users, batch, "5.05")
        assert approved.status_code == 200, approved.data
    finally:
        resume.set()
        thread.join(10)
    assert not thread.is_alive()
    assert "error" not in result, result
    assert result["response"].status_code == 409
    db.session.expire_all()
    after = view(client, batch)
    assert after["status"] == "approved"
    assert after["version"] == approved.json["version"]
    assert after["rows"][0]["status"] == "approved"
    login(client, users["student"])
    second = upload(client, color="gray")
    run_one(app, Provider(credit(day="22")))
    submit(client, second)
    assert approve(client, users, second, "5.05").status_code == 200
    db.session.expire_all()
    assert Decimal(str(Student.query.first().comprehensive_performance_total)) == Decimal("1")
    assert db.session.get(Application, submitted["application_id"]).final_score == .505


def test_partial_submission_can_continue_without_reupload(env):
    app, client, users = env
    policy(client, users, max_score="10")
    batch = bulk(client)
    run_one(app, TwoCredits())
    before = view(client, batch)
    remaining_id = before["rows"][1]["id"]
    remaining_image = client.get(before["rows"][1]["image_url"]).data
    response = client.post(f"/api/automation/volunteer/batches/{batch}/submit", json={
        "version": before["version"], "item_ids": [before["rows"][0]["id"]],
    })
    assert response.status_code == 201, response.data
    child = response.json["remaining_batch_id"]
    assert child and child != batch
    remaining = view(client, child)
    assert remaining["source_batch_id"] == batch
    assert [row["id"] for row in remaining["rows"]] == [remaining_id]
    assert remaining["rows"][0]["can_submit"]
    assert client.get(remaining["rows"][0]["image_url"]).data == remaining_image
    assert AutomationFingerprint.query.filter_by(item_id=remaining_id).count() >= 2
    assert submit(client, child)["application_id"] != response.json["application_id"]
    assert approve(client, users, batch, "5.05").status_code == 200
    assert approve(client, users, child, "5.05").status_code == 200
    db.session.expire_all()
    assert Student.query.first().comprehensive_performance_total == 1.01
    assert AutomationReview.query.filter_by(batch_id=batch).count() == 2


@pytest.mark.parametrize("bad_hours", ["+100001", "+5.00001", "+5.00000000000000001", "+" + "9" * 400])
def test_invalid_ocr_isolated_and_remaining_can_retry(env, bad_hours):
    app, client, users = env
    policy(client, users)
    batch = bulk(client)
    run_one(app, TwoCredits(second_hours=bad_hours))
    report = view(client, batch)
    assert report["rows"][0]["status"] == "ready"
    assert report["rows"][1]["status"] == "incomplete"
    assert not report["rows"][1]["can_submit"]
    assert report["rows"][1]["requested_hours"] is None
    response = client.post(f"/api/automation/volunteer/batches/{batch}/submit", json={
        "version": report["version"], "item_ids": [report["rows"][0]["id"]],
    })
    assert response.status_code == 201, response.data
    child = response.json["remaining_batch_id"]
    assert client.post(f"/api/automation/volunteer/batches/{child}/retry",
                       json={"version": view(client, child)["version"]}).status_code == 202
    run_one(app, Provider(credit(day="22")))
    assert view(client, child)["rows"][0]["status"] == "ready"
    assert submit(client, child)["application_id"]


def test_invalid_legacy_ocr_does_not_break_preview(env):
    app, client, users = env
    policy(client, users)
    batch = upload(client)
    run_one(app, Provider(credit()))
    item = AutomationItem.query.filter_by(batch_id=batch).one()
    report = dict(item.report)
    report["fields"] = dict(report["fields"])
    report["fields"]["displayed_hours"] = {**report["fields"]["displayed_hours"], "value": 100001}
    item.report = report
    db.session.commit()
    response = client.get(f"/api/automation/volunteer/batches/{batch}")
    assert response.status_code == 200
    assert not response.json["rows"][0]["can_submit"]


def test_honor_same_recorded_timestamp_different_activity_not_duplicate(env):
    app, client, users = env
    policy(client, users)
    first = upload(client, kind="honor")
    data = honor()
    data["rec_texts"][-1] = "2025.12.21 活动A"
    run_one(app, Provider(data))
    second = upload(client, color="gray", kind="honor")
    data = honor()
    data["rec_texts"][-1] = "2025.12.22 活动B"
    run_one(app, Provider(data))
    assert view(client, first)["rows"][0]["status"] == "ready"
    assert view(client, second)["rows"][0]["status"] == "ready"
    submit(client, first)
    submit(client, second)
    assert approve(client, users, first, "11.5").status_code == 200
    assert approve(client, users, second, "11.5").status_code == 200


@pytest.mark.parametrize("bad", [[], {}, True, 1, None])
def test_malformed_material_type_returns_400(env, bad):
    app, client, users = env
    policy(client, users)
    batch = upload(client)
    run_one(app, Provider(credit()))
    before = view(client, batch)
    response = client.post(f"/api/automation/volunteer/batches/{batch}/reclassify",
                           json={"version": before["version"], "material_type": bad})
    assert response.status_code == 400
    assert view(client, batch)["version"] == before["version"]


@pytest.mark.parametrize("bad", [[], {}, True, "1", None, 1.0])
def test_malformed_review_id_returns_400_without_mutation(env, bad):
    app, client, users = env
    policy(client, users)
    batch = upload(client)
    run_one(app, Provider(credit()))
    report = submit(client, batch)
    login(client, users["admin"])
    response = client.post(f"/api/automation/volunteer/batches/{batch}/review", json={
        "version": report["version"], "status": "approved",
        "items": [{"id": bad, "decision": "approved", "confirmed_hours": "5.05"}],
    })
    assert response.status_code == 400
    db.session.expire_all()
    assert view(client, batch)["version"] == report["version"]
    assert db.session.get(Application, report["application_id"]).final_score is None


@pytest.mark.parametrize("claim,expected", [("15", 202), ("15.0001", 400), ("16", 400)])
def test_credit_claim_15_hour_boundary(env, claim, expected):
    app, client, users = env
    policy(client, users)
    response = client.post("/api/automation/volunteer/batches", data={
        "material_type": "credit", "year": "2025", "claimed_hours": f"[{claim}]",
        "files": (io.BytesIO(image_bytes()), "example.png"),
    })
    assert response.status_code == expected


def test_credit_screenshot_over_15_preserves_ocr_and_caps_request_and_review(env):
    app, client, users = env
    policy(client, users, max_score="10")
    batch = upload(client)
    data = credit(hours="+17", end="05:33:03")
    data["rec_texts"][5] = "2025年12月22日"
    run_one(app, Provider(data))
    report = view(client, batch)
    assert report["rows"][0]["displayed_hours"] == 17
    assert report["rows"][0]["requested_hours"] == "15"
    assert report["estimated_incremental_score"] == "1.5000"
    assert report["rows"][0]["credit_max_hours"] == "15"
    submitted = submit(client, batch)
    assert db.session.get(Application, submitted["application_id"]).self_score == 1.5
    dates = ["2025-12-21", "2025-12-22"]
    response = approve(client, users, batch, "15.0001", dates)
    assert response.status_code == 400
    assert view(client, batch)["version"] == submitted["version"]
    assert approve(client, users, batch, "15", dates).status_code == 200


def test_honor_is_not_subject_to_credit_15_hour_limit(env):
    app, client, users = env
    policy(client, users, max_score="10")
    batch = upload(client, kind="honor", claim=20)
    data = honor()
    data["rec_texts"][1] = "20"
    run_one(app, Provider(data))
    assert view(client, batch)["rows"][0]["credit_max_hours"] is None
    submit(client, batch)
    assert approve(client, users, batch, "20").status_code == 200


@pytest.mark.parametrize("first_kind", ["credit", "honor"])
def test_same_activity_cross_type_is_blocked_in_both_upload_orders(env, first_kind):
    app, client, users = env
    policy(client, users, max_score="10")
    honor_data = honor()
    honor_data["rec_texts"][1] = "5.05"
    honor_data["rec_texts"][-1] = "2025.12.21 志愿服务活动"
    first = upload(client, kind=first_kind)
    run_one(app, Provider(credit() if first_kind == "credit" else honor_data))
    second = upload(client, kind="honor" if first_kind == "credit" else "credit", color="gray")
    run_one(app, Provider(honor_data if first_kind == "credit" else credit()))
    assert view(client, first)["rows"][0]["can_submit"]
    assert view(client, second)["rows"][0]["status"] == "duplicate"
    assert client.post(f"/api/automation/volunteer/batches/{second}/submit",
                       json={"version": view(client, second)["version"]}).status_code == 400


def test_uncertain_cross_type_overlap_requires_explicit_distinct_confirmation(env):
    app, client, users = env
    policy(client, users, max_score="10")
    first = upload(client)
    run_one(app, Provider(credit()))
    first_id = view(client, first)["rows"][0]["id"]
    second = upload(client, kind="honor", color="gray")
    run_one(app, Provider(honor()))
    report = submit(client, second)
    login(client, users["admin"])
    detail = {"id": report["rows"][0]["id"], "decision": "approved", "confirmed_hours": "11.5",
              "comment": "已核对两份平台活动详情，确认属于不同活动"}
    payload = {"version": report["version"], "status": "approved", "items": [detail]}
    assert client.post(f"/api/automation/volunteer/batches/{second}/review", json=payload).status_code == 400
    detail["distinct_activity_ids"] = [first_id]
    response = client.post(f"/api/automation/volunteer/batches/{second}/review", json=payload)
    assert response.status_code == 200, response.data


def test_added_honor_dates_recheck_cross_type_duplicate_at_review(env):
    app, client, users = env
    policy(client, users, max_score="10")
    first = upload(client)
    run_one(app, Provider(credit()))
    first_id = view(client, first)["rows"][0]["id"]
    second = upload(client, kind="honor", color="gray")
    data = honor()
    data["rec_texts"][-1] = "志愿服务活动"
    run_one(app, Provider(data))
    report = submit(client, second)
    login(client, users["admin"])
    response = client.post(f"/api/automation/volunteer/batches/{second}/review", json={
        "version": report["version"], "status": "approved", "items": [{
            "id": report["rows"][0]["id"], "decision": "approved", "confirmed_hours": "11.5",
            "activity_dates": ["2025-12-21"], "comment": "补充活动日期，仍必须阻止同一活动双计",
            "distinct_activity_ids": [first_id],
        }],
    })
    assert response.status_code == 409
    assert view(client, second)["status"] == "submitted"


def test_prose_honor_reason_cannot_silently_bypass_cross_type_check(env):
    app, client, users = env
    policy(client, users, max_score="10")
    first = upload(client)
    run_one(app, Provider(credit()))
    first_id = view(client, first)["rows"][0]["id"]
    second = upload(client, kind="honor", color="gray")
    data = honor()
    data["rec_texts"][-1] = "2025.12.21 参加志愿服务活动的补录"
    run_one(app, Provider(data))
    row = view(client, second)["rows"][0]
    assert row["cross_type_conflicts"][0]["id"] == first_id
    assert row["cross_type_conflicts"][0]["match"] == "needs_verification"
    submit(client, second)
    assert approve(client, users, second, "11.5").status_code == 400


@pytest.mark.parametrize("bad", [[], {}, True, None, 1.0, "2"])
def test_invalid_version_does_not_modify_batch(env, bad):
    app, client, users = env
    policy(client, users)
    batch = upload(client)
    run_one(app, Provider(credit()))
    before = view(client, batch)
    response = client.post(f"/api/automation/volunteer/batches/{batch}/submit", json={"version": bad})
    assert response.status_code == 409
    assert view(client, batch)["version"] == before["version"]
    assert Application.query.count() == 0


def test_worker_never_claims_linked_application_even_if_status_corrupt(env):
    app, client, users = env
    policy(client, users)
    batch = upload(client)
    run_one(app, Provider(credit()))
    submit(client, batch)
    record = db.session.get(AutomationBatch, batch)
    record.status = "queued"
    db.session.commit()

    class Unexpected:
        def predict(self, path):
            raise AssertionError("已关联申请的批次不能被识别任务处理")

    assert run_one(app, Unexpected()) is False


def test_remaining_wrong_type_can_correct_type_with_original_item_and_file(env):
    app, client, users = env
    policy(client, users)
    batch = bulk(client)

    class Mixed:
        count = 0
        def predict(self, path):
            self.count += 1
            return credit() if self.count == 1 else honor()

    run_one(app, Mixed())
    original = view(client, batch)["rows"][1]
    report = submit(client, batch)
    child = report["remaining_batch_id"]
    before = view(client, child)
    response = client.post(f"/api/automation/volunteer/batches/{child}/reclassify", json={
        "version": before["version"], "material_type": "honor",
    })
    assert response.status_code == 202
    run_one(app, Provider(honor()))
    assert view(client, child)["rows"][0]["id"] == original["id"]
    assert view(client, child)["rows"][0]["status"] == "ready"
    assert submit(client, child)["application_id"]


def test_legacy_honor_record_with_manual_dates_still_deduplicates(env):
    app, client, users = env
    policy(client, users)
    first = upload(client, kind="honor")
    data = honor()
    data["rec_texts"][-1] = "文艺演出"
    run_one(app, Provider(data))
    submit(client, first)
    assert approve(client, users, first, "11.5", ["2025-12-21"]).status_code == 200
    item = AutomationItem.query.filter_by(batch_id=first).one()
    # 模拟旧版数据库只有录入时间粗键，而活动日期来自人工补充的情形。
    AutomationFingerprint.query.filter(AutomationFingerprint.item_id == item.id,
                                        AutomationFingerprint.kind != "file").delete(synchronize_session=False)
    facts = ["honor", item.report["fields"]["recorded_at"]["value"], "张三", "担保书补录"]
    digest = hashlib.sha256(json.dumps(facts, ensure_ascii=False).encode()).hexdigest()
    db.session.add(AutomationFingerprint(student_id="S1", kind="activity", value=digest, item_id=item.id))
    db.session.commit()
    login(client, users["student"])
    second = upload(client, kind="honor", color="gray")
    run_one(app, Provider(data))
    assert view(client, second)["rows"][0]["status"] == "duplicate"
