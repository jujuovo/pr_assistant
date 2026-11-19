import json
from pathlib import Path


def test_openapi_documents_backend_authority_and_version_conflicts():
    path = Path(__file__).parents[1] / "docs/openapi-materials.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    contract = spec["x-authority-contract"]
    assert contract["source_of_truth"] == "backend"
    assert {"version", "status", "scope", "reason_code", "updated_at",
            "allowed_actions"} <= set(contract["presentation_fields"])
    assert "comprehensive_score" in contract["derived_read_only_fields"]
    assert "409" in contract["version_conflict"]
