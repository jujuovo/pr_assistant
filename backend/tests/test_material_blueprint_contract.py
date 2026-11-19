from conftest import login
import pytest

pytestmark = pytest.mark.usefixtures("active_honor_rule")


HONOR = {
    "honor_name": "优秀学生干部",
    "honor_level": "校级",
    "issuer": "学校",
    "award_date": "2026-06-01",
}


def test_blueprint_exposes_actions_conflicts_and_idempotent_review(env):
    _app, client, users = env
    login(client, users["student"])
    created = client.post(
        "/api/materials/honor/records",
        json={"year": 2026, "data": HONOR},
    )
    assert created.status_code == 201
    assert {"edit", "add_attachment", "submit"} <= set(created.json["allowed_actions"])
    record_id = created.json["id"]
    submitted = client.post(
        f"/api/materials/honor/records/{record_id}/submit", json={"version": 1}
    )
    assert submitted.status_code == 200
    assert "withdraw" in submitted.json["allowed_actions"]
    stale = client.patch(
        f"/api/materials/honor/records/{record_id}",
        json={"version": 1, "data": HONOR},
    )
    assert stale.status_code == 409 and stale.json["code"] == "invalid_transition"

    login(client, users["admin"])
    payload = {
        "version": 2,
        "decision": "verified",
        "comment": "已核验",
        "idempotency_key": "http-review-1",
    }
    reviewed = client.post(f"/api/materials/honor/records/{record_id}/review", json=payload)
    assert reviewed.status_code == 200 and reviewed.json["replayed"] is False
    assert reviewed.json["overall_status"] == "complete"
    assert reviewed.json["verification_status"] == "verified"
    assert reviewed.json["scoring_status"] == "scored"
    assert reviewed.json["cycle"]["cycle_code"] == 2026
    assert "review" not in reviewed.json["allowed_actions"]
    replay = client.post(f"/api/materials/honor/records/{record_id}/review", json=payload)
    assert replay.status_code == 200 and replay.json["replayed"] is True


def test_unavailable_recognition_does_not_block_manual_review(env):
    _app, client, users = env
    login(client, users["student"])
    created = client.post(
        "/api/materials/honor/records",
        json={"year": 2026, "data": HONOR},
    ).json
    record_id = created["id"]
    recognition = client.post(f"/api/materials/honor/records/{record_id}/recognize")
    assert recognition.status_code == 501
    assert recognition.json["ocr_executed"] is False
    detail = client.get(f"/api/materials/honor/records/{record_id}").json
    assert detail["status"] == "draft" and detail["data"] == created["data"]
    submitted = client.post(
        f"/api/materials/honor/records/{record_id}/submit", json={"version": 1}
    )
    assert submitted.status_code == 200
    login(client, users["admin"])
    reviewed = client.post(
        f"/api/materials/honor/records/{record_id}/review",
        json={
            "version": 2,
            "decision": "verified",
            "comment": "OCR不可用，已人工核对原件",
            "idempotency_key": "manual-after-ocr-failure",
        },
    )
    assert reviewed.status_code == 200 and reviewed.json["status"] == "scored"
    assert reviewed.json["scoring_status"] == "scored"

