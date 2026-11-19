from pathlib import Path

from workflow_models import (
    RankingBatch,
    RankingEntry,
    RuleVersion,
    ScoreEntry,
    StudentScoreSnapshot,
    RankingExportAudit,
    RecommendationCyclePolicy,
    ReviewScoringCommand,
    ScoreOverrideAudit,
)


ROOT = Path(__file__).resolve().parents[2]


def test_data_model_document_matches_orm_columns_and_migrations():
    content = (ROOT / "docs/workflow-data-model.md").read_text(encoding="utf-8")
    for model in (
        RuleVersion,
        ScoreEntry,
        StudentScoreSnapshot,
        RankingBatch,
        RankingEntry,
        RankingExportAudit,
        RecommendationCyclePolicy,
        ReviewScoringCommand,
        ScoreOverrideAudit,
    ):
        assert f"`{model.__name__}`" in content
        for column in model.__table__.columns:
            assert f"`{column.name}`" in content, (model.__name__, column.name)
    for migration in (
        "20261104_rule_version.py",
        "20261104_score_entry.py",
        "20261104_score_snapshot.py",
        "20261104_ranking_models.py",
        "20261104_review_command.py",
        "20261104_snapshot_caps.py",
        "20261104_ranking_export_audit.py",
        "20261105_cycle_policy.py",
        "20261105_review_scoring_command.py",
        "20261105_score_override_audit.py",
    ):
        assert (ROOT / "backend/migrations/versions" / migration).is_file()
        assert f"`{migration}`" in content

