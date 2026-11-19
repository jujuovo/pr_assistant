from pathlib import Path


def test_competition_contract_documents_new_authority_and_legacy_boundary():
    root = Path(__file__).resolve().parents[2]
    api = (root / "backend/docs/competition-2028-api.md").read_text(encoding="utf-8")
    operations = (root / "docs/competition-2028-operations.md").read_text(encoding="utf-8")
    assert "MaterialRecord -> CompetitionRulePackage -> ScoreEntry" in api
    assert "competition_material_route_required" in api
    assert "尚未迁移类别" in api and "退出条件" in api
    assert "RESET-COMPETITION-2028" in operations
    assert "SQLite 结果不得替代 PostgreSQL" in operations


def test_competition_write_contract_does_not_declare_legacy_authoritative_fields():
    root = Path(__file__).resolve().parents[2]
    api = (root / "backend/docs/competition-2028-api.md").read_text(encoding="utf-8")
    write_section = api.split("## 竞赛写入字段", 1)[1].split("##", 1)[0]
    for field in (
        "rule_id", "self_score", "final_score", "dynamic_coefficients",
        "override_score", "override_reason",
    ):
        assert f"`{field}`" not in write_section
