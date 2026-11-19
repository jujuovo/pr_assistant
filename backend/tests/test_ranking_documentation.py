from pathlib import Path


def test_ranking_documentation_covers_full_lifecycle_and_audit():
    text=(Path(__file__).resolve().parents[2]/"docs/ranking-publication.md").read_text(encoding="utf-8")
    for status in ("draft","stale","frozen","published","withdrawn"):
        assert f"`{status}`" in text
    assert "1, 1, 3" in text
    assert "predecessor_batch_id" in text
    assert "purpose" in text
