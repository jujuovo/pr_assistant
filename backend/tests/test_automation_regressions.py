"""计分、选择提交和重复材料展示的回归测试；不连接业务数据库。"""
import io
from decimal import Decimal

import pytest
from PIL import Image

from conftest import login
from extensions import db
from models import Application, Student
from automation_models import AutomationItem
from services.recognition.worker import run_one
from test_automation import (Provider, approve, credit, image_bytes, policy,
                             submit, upload, view)


def approved_credit(app, client, users, *, color="white", day="21", hours="5.05",
                    end="17:36:34"):
    login(client, users["student"])
    batch = upload(client, color=color)
    assert run_one(app, Provider(credit(hours="+" + hours, day=day, end=end)))
    report = submit(client, batch)
    response = approve(client, users, batch, hours)
    assert response.status_code == 200, response.data
    return batch, report["application_id"]


def test_preview_uses_same_half_up_rounding_as_approval(env):
    app, client, users = env
    policy(client, users, credit_rate="0.0001", max_score="0.0001")
    batch = upload(client)
    run_one(app, Provider(credit(hours="+0.5", end="13:03:03")))
    before = view(client, batch)
    assert before["final_score"] is None
    submit(client, batch)
    response = approve(client, users, batch, "0.5")
    assert response.status_code == 200, response.data
    actual = Decimal(str(db.session.get(Application, response.json["application_id"]).final_score))
    assert Decimal(response.json["final_score"]) == actual
    assert Decimal(before["rows"][0]["estimated_score_before_cap"]) == actual == Decimal("0.0001")
    assert Decimal(before["estimated_incremental_score"]) == actual


def test_rounding_cannot_exceed_small_annual_cap(env):
    app, client, users = env
    policy(client, users, credit_rate="0.0001", max_score="0.0001")
    first, first_app = approved_credit(app, client, users, hours="0.5", end="13:03:03")
    second, second_app = approved_credit(app, client, users, color="gray", day="22",
                                         hours="0.5", end="13:03:03")
    db.session.expire_all()
    scores = [Decimal(str(db.session.get(Application, key).final_score)) for key in (first_app, second_app)]
    assert scores == [Decimal("0.0001"), Decimal("0.0000")]
    assert sum(scores) == Decimal("0.0001")
    assert Decimal(str(Student.query.first().comprehensive_performance_total)) == sum(scores)
    assert view(client, first)["estimated_incremental_score"] == "0.0001"
    assert view(client, second)["estimated_incremental_score"] == "0.0000"


def test_rounding_cannot_exceed_normal_annual_cap(env):
    app, client, users = env
    policy(client, users, max_score="1")
    application_ids = []
    for day in range(1, 10):
        _, application_id = approved_credit(app, client, users, color=(day, 0, 0),
                                             day=f"{day:02d}", hours="1.2345", end="13:47:07")
        application_ids.append(application_id)
    db.session.expire_all()
    total = sum((Decimal(str(db.session.get(Application, key).final_score)) for key in application_ids), Decimal(0))
    assert total == Decimal("1.0000")
    assert Decimal(str(Student.query.first().comprehensive_performance_total)) == total


def test_approved_preview_follows_allocated_score_and_revocation(env):
    app, client, users = env
    policy(client, users)
    first, first_app = approved_credit(app, client, users)
    second, second_app = approved_credit(app, client, users, color="gray", day="22")
    for batch, application_id in ((first, first_app), (second, second_app)):
        report = view(client, batch)
        assert Decimal(report["estimated_incremental_score"]) == Decimal(str(db.session.get(Application, application_id).final_score))
        assert report["final_score"] == report["estimated_incremental_score"]
    response = client.post(f"/api/automation/volunteer/batches/{first}/review",
                           json={"version": view(client, first)["version"], "status": "rejected"})
    assert response.status_code == 200, response.data
    assert response.json["estimated_incremental_score"] == "0.0000"
    assert response.json["final_score"] == "0.0000"
    assert view(client, second)["estimated_incremental_score"] == "0.5050"


def test_activity_duplicate_shows_its_own_uploaded_image(env):
    app, client, users = env
    policy(client, users)
    original = upload(client)
    run_one(app, Provider(credit()))
    altered = upload(client, color="gray")
    run_one(app, Provider(credit(hours="+50")))
    row = view(client, altered)["rows"][0]
    assert row["status"] == "duplicate"
    assert row["duplicate_of"] == view(client, original)["rows"][0]["id"]
    response = client.get(row["image_url"])
    assert response.status_code == 200
    assert response.data == image_bytes("gray")
    assert response.headers["Cache-Control"] == "private, no-store"
    login(client, users["other"])
    assert client.get(row["image_url"]).status_code == 403


def test_identical_file_duplicate_still_shows_original_bytes(env):
    app, client, users = env
    policy(client, users)
    upload(client)
    repeated = upload(client)
    row = view(client, repeated)["rows"][0]
    assert row["status"] == "duplicate"
    assert db.session.get(AutomationItem, row["id"]).stored_name is None
    response = client.get(row["image_url"])
    assert response.status_code == 200
    assert response.data == image_bytes()


@pytest.mark.parametrize("cap,prior_hours,selected_index,expected", [
    ("10", None, 0, "0.5050"),
    ("10", None, 1, "0.2000"),
    ("0.6", "2.0", 0, "0.4000"),
    ("0.6", "2.0", 1, "0.2000"),
])
def test_partial_submission_saves_only_selected_score(env, cap, prior_hours, selected_index, expected):
    app, client, users = env
    policy(client, users, max_score=cap)
    if prior_hours:
        approved_credit(app, client, users, color="black", day="20", hours=prior_hours, end="14:33:03")
        login(client, users["student"])
    response = client.post("/api/automation/volunteer/batches", data={
        "material_type": "credit", "year": "2025",
        "files": [(io.BytesIO(image_bytes()), "first.png"),
                  (io.BytesIO(image_bytes("gray")), "second.png")],
    })
    assert response.status_code == 202, response.data
    batch = response.json["id"]

    class ByColor:
        def predict(self, path):
            with Image.open(path) as image:
                return credit() if image.getpixel((0, 0)) == (255, 255, 255) else credit(hours="+2.0", day="22", end="14:33:03")

    run_one(app, ByColor())
    before = view(client, batch)
    selected_id = before["rows"][selected_index]["id"]
    response = client.post(f"/api/automation/volunteer/batches/{batch}/submit",
                           json={"version": before["version"], "item_ids": [selected_id]})
    assert response.status_code == 201, response.data
    db.session.expire_all()
    application = db.session.get(Application, response.json["application_id"])
    assert Decimal(str(application.self_score)) == Decimal(expected)
    assert response.json["estimated_incremental_score"] == expected
    assert [row["id"] for row in response.json["rows"] if row["submitted"]] == [selected_id]
