from decimal import Decimal

import pytest
from domain.research_scoring import candidate

PAPER = dict(title="测试论文", work_key="doi:1", first_institution="厦门大学", authors=["甲"],
             student_author="甲", venue="会议", proof_date="2028-08-31", published=True, indexed=True,
             article_type="full_article", cofirst_authors=[], ccf_grade="A", ccf_version="核定版",
             ccf_entry="会议", directory_basis="条目1")


@pytest.mark.parametrize("changes,expected", [
    ({}, "10"),
    (dict(ccf_grade="B", authors=["导师", "乙", "甲"], mentor="导师"), "1.2"),
    (dict(authors=["甲", "乙"], cofirst_authors=["甲", "乙"]), "5"),
    (dict(authors=["乙", "甲"], cofirst_authors=["甲", "乙"]), "5"),
    (dict(venue="Cell Reports", verified_family="CELL", if_year=2025, impact_factor="10"), "20"),
    (dict(venue="Cell Reports", verified_family="CELL", if_year=2025, impact_factor="9.99",
          ccf_entry="Cell Reports", ccf_grade="B"), "6"),
    (dict(proof_date="2028-09-02"), "0"),
    (dict(venue="软件学报"), "6"),
    (dict(venue="IEEE Transactions on Mobile Computing"), "10"),
    (dict(venue="IEEE Transactions on Information Forensics and Security"), "0"),
    (dict(indexed=False), "0"), (dict(article_type="review"), "0"),
])
def test_paper(changes, expected):
    assert candidate("research_paper", PAPER | changes, "2028-08-31")[0] == Decimal(expected)


@pytest.mark.parametrize("changes,expected", [
    ({}, "2"), (dict(authors=["甲", "乙"]), "1.6"), (dict(authorized_national_invention=False), "0"),
    (dict(first_institution="其他单位"), "0"), (dict(certificate_date="2028-09-01"), "0"),
])
def test_patent(changes, expected):
    facts = dict(authorized_national_invention=True, certificate_date="2028-08-31",
                 first_institution="厦门大学", student_author="甲", authors=["甲"])
    assert candidate("invention_patent", facts | changes, "2028-08-31")[0] == Decimal(expected)
