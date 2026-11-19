from pathlib import Path


def test_unified_review_documentation_records_contract_and_transaction_boundary():
    content = (Path(__file__).resolve().parents[2] / "docs/auditable-scoring.md").read_text(
        encoding="utf-8"
    )
    for term in (
        "use_cases.materials.review_material",
        "source_type + source_id + source_version",
        "idempotency_conflict",
        "cycle_policy_missing",
        "override_reason_required",
        "snapshot_failed",
        "overall_status",
        "verification_status",
        "scoring_status",
        "allowed_actions",
        "整个审核计分事务回滚",
    ):
        assert term in content
