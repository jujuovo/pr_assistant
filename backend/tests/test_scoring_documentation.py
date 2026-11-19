from decimal import Decimal
from pathlib import Path

from domain.scoring import ScoreFact, build_score_projection


def test_documented_cap_example_matches_scoring_policy():
    projection = build_score_projection(
        90,
        [
            ScoreFact(1, "academic", Decimal("10"), 1),
            ScoreFact(2, "academic", Decimal("8"), 2),
            ScoreFact(3, "comprehensive", Decimal("7"), 3),
        ],
        academic_weight=80,
        specialty_max=15,
        performance_max=5,
    )
    assert projection.specialty_raw_score == Decimal("18.0000")
    assert projection.specialty_score == Decimal("15.0000")
    assert projection.performance_raw_score == Decimal("7.0000")
    assert projection.performance_score == Decimal("5.0000")
    assert projection.comprehensive_score == Decimal("92.0000")
    document = (Path(__file__).resolve().parents[2] / "docs/auditable-scoring.md").read_text(
        encoding="utf-8"
    )
    assert "90 * 80% + 15 + 5 = 92" in document
    assert "preview:true" in document

