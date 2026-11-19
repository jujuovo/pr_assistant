from datetime import date, datetime

import pytest

from services.workflow_schemas import (
    cycle_policy_dto, material_presentation_dto, ranking_batch_dto,
    ranking_presentation_dto, rule_package_presentation_dto,
    score_presentation_dto, score_snapshot_dto,
)


def test_score_contract_has_one_unambiguous_total_field():
    payload = score_snapshot_dto({"student_id":"S1", "year":2026, "status":"current",
        "base":{}, "categories":{}, "comprehensive_score":"80.0000", "formula":"x",
        "rule_version_ids":[], "cycle_policy_version_ids":[],
        "input_digest":"d", "updated_at":"now", "entries":[]})
    assert payload["comprehensive_score"] == "80.0000"
    assert "total_score" not in payload and "final_score" not in payload


def test_ranking_contract_uses_batch_and_comprehensive_score_names():
    class Batch:
        id=1; year=2026; status="draft"; version=1; scope_definition={}
        rule_version_ids=[]; stale_reason=None; published_at=None
        class created_at:
            @staticmethod
            def isoformat(): return "2026-01-01T00:00:00"
    class Entry:
        student_id="S1"; frozen_score=80; rank=1; display_order=1
        eligible=True; exclusion_reason=None
    dto = ranking_batch_dto(Batch(), [Entry()])
    assert dto["batch_id"] == 1 and dto["entries"][0]["comprehensive_score"] == "80"
    assert "score" not in dto["entries"][0]


def test_cycle_policy_contract_exposes_stable_global_context():
    class Policy:
        cycle_code = 2026
        display_name = "2026 推免周期"
        version = 2
        status = "active"
        eligible_award_start_date = date(2023, 9, 1)
        eligible_award_end_date = date(2026, 8, 31)
        boundary = "inclusive"
        activated_at = datetime(2026, 1, 2, 3, 4, 5)

    assert cycle_policy_dto(Policy()) == {
        "cycle_code": 2026,
        "display_name": "2026 推免周期",
        "policy_version": 2,
        "status": "active",
        "eligible_award_start_date": "2023-09-01",
        "eligible_award_end_date": "2026-08-31",
        "boundary": "inclusive",
        "activated_at": "2026-01-02T03:04:05Z",
    }


def test_presentation_dtos_have_common_authority_envelope_and_trim_actions():
    common = {"student_id": "S1", "faculty_id": 1, "year": 2029,
              "status": "submitted", "version": 3, "updated_at": "now",
              "allowed_actions": ["view", "approve", "publish"]}
    material = material_presentation_dto(
        {**common, "id": 8, "category": "competition", "data": {"project_name": "P"}},
        role="teacher", faculty_id=1,
    )
    score = score_presentation_dto(
        {**common, "snapshot_id": 4, "snapshot_version": 2,
         "comprehensive_score": "88", "categories": {}, "entries": []},
        role="student", student_id="S1",
    )
    package = rule_package_presentation_dto(
        {"id": 2, "package_id": "competition-2029", "cycle_code": 2029,
         "scope_key": "global", "version": 1, "status": "draft",
         "allowed_actions": ["copy", "edit", "freeze"]}, role="admin", faculty_id=1,
    )
    for dto in (material, score, package):
        assert {"kind", "version", "status", "scope", "reason_code",
                "allowed_actions"} <= dto.keys()
    assert material["allowed_actions"] == ["approve", "view"]
    assert score["allowed_actions"] == ["view"]
    assert package["allowed_actions"] == ["copy", "edit"]


def test_role_trimming_and_organization_scope_protect_ranking_entries():
    batch = {"id": 9, "student_id": "S1", "faculty_id": 1, "version": 2,
             "status": "frozen", "scope_definition": {"faculty_id": 1, "major_id": 3},
             "allowed_actions": ["view", "freeze", "publish", "export"]}
    entries = [
        {"student_id": "S1", "frozen_score": 90, "rank": 1, "eligible": True},
        {"student_id": "S2", "frozen_score": 80, "rank": 2, "eligible": True},
    ]
    student = ranking_presentation_dto(batch, entries, role="student", student_id="S1")
    teacher = ranking_presentation_dto(batch, entries, role="teacher", faculty_id=1)
    admin = ranking_presentation_dto(batch, entries, role="admin", faculty_id=1)
    assert [row["student_id"] for row in student["entries"]] == ["S1"]
    assert len(teacher["entries"]) == 2 and teacher["allowed_actions"] == ["export", "view"]
    assert admin["allowed_actions"] == ["export", "freeze", "publish", "view"]
    with pytest.raises(PermissionError):
        ranking_presentation_dto(batch, entries, role="teacher", faculty_id=2)
    with pytest.raises(PermissionError):
        score_presentation_dto({"student_id": "S1", "faculty_id": 1},
                               role="student", student_id="S2")
