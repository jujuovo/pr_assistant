import json
from pathlib import Path


def test_ranking_openapi_defines_states_scope_versions_and_times():
    root = Path(__file__).parents[1]
    spec = json.loads((root / "docs/openapi-workflow.json").read_text(encoding="utf-8"))
    contract = spec["x-ranking-contract"]
    assert "correction_required" in contract["states"]
    assert {"generate", "freeze", "request_correction", "publish", "withdraw",
            "create_successor"} <= set(contract["commands"])
    assert {"scope", "status", "version", "generated_at", "updated_at",
            "published_at"} <= set(contract["presentation_fields"])
    assert {"RankingCommand", "RankingStateEvent", "RankingExportAudit"} <= set(contract["audit"])


def test_ranking_state_diagram_documents_correction_and_successor_rules():
    text = (Path(__file__).parents[2] / "docs/ranking-publication.md").read_text(encoding="utf-8")
    for phrase in ("correction_required", "修正权威来源", "idempotency_key",
                   "学生 DTO 只含本人", "教师为授权范围完整只读"):
        assert phrase in text
