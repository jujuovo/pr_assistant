from decimal import Decimal
import pytest
from domain.innovation_scoring import candidate


@pytest.mark.parametrize("level,role,expected", [
    ("national", "leader", "1"), ("national", "member", "0.3"),
    ("provincial", "leader", "0.5"), ("provincial", "member", "0.2"),
    ("university", "leader", "0.1"), ("university", "member", "0.05"),
])
def test_candidate(level, role, expected):
    facts = dict(completed=True, completion_date="2028-08-31", level=level, role=role)
    assert candidate("innovation_training", facts, "2028-08-31")[0] == Decimal(expected)
