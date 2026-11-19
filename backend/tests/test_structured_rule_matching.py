from domain.structured_rules import RuleCandidate, match_structured_rules


BASE = {
    "competition_name": "蓝桥杯", "competition_level": "省级",
    "region": "福建赛区", "group": "软件类大学B组", "track": None,
}


def candidate(version_id, award_level, score=5, **changes):
    values = dict(
        version_id=version_id, cycle_code=2026, faculty_id=1,
        material_category="competition",
        terms={**BASE, "award_level": award_level}, score=score,
    )
    values.update(changes)
    return RuleCandidate(**values)


def match(candidates, terms):
    return match_structured_rules(
        candidates, cycle_code=2026, faculty_id=1,
        material_category="competition", terms=terms,
    )


def test_unique_exact_match_returns_explanation():
    result = match(
        [candidate(1, "一等奖"), candidate(2, "三等奖", 2)],
        {**BASE, "award_level": "三等奖"},
    )
    assert result["status"] == "matched"
    assert result["match"]["version_id"] == 2
    assert result["match"]["score"] == 2
    assert result["match"]["dimensions"]["award_level"]["mode"] == "exact"


def test_third_prize_never_falls_back_to_first_or_unstructured_default():
    result = match(
        [candidate(1, "一等奖"), RuleCandidate(
            version_id=9, cycle_code=2026, faculty_id=1,
            material_category="competition", terms={}, score=5,
        )],
        {**BASE, "award_level": "三等奖"},
    )
    assert result["status"] == "unmapped"
    assert result["reason"] == "material_terms_unmapped"
    assert not any(item["matched"] for item in result["evaluated"])


def test_multiple_exact_matches_are_ambiguous_not_first_match():
    result = match(
        [candidate(7, "三等奖", 2), candidate(3, "三等奖", 5)],
        {**BASE, "award_level": "三等奖"},
    )
    assert result["status"] == "ambiguous"
    assert result["reason"] == "ambiguous_scoring_rules"
    assert result["rule_version_ids"] == [3, 7]


def test_global_faculty_and_explicit_any_are_intentional():
    rule = candidate(4, "三等奖", faculty_id=None, terms={
        **BASE, "region": {"any": True}, "award_level": "三等奖",
    })
    result = match([rule], {**BASE, "region": "广东赛区", "award_level": "三等奖"})
    assert result["status"] == "matched"
    assert result["match"]["dimensions"]["region"]["mode"] == "explicit_any"
