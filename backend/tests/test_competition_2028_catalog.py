import hashlib
import json
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parents[1] / "rules" / "competition_2028.json"


def load_package():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def canonical_digest(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_formal_catalog_is_atomic_complete_and_stable():
    package = load_package()
    catalog = package["catalog"]

    assert len(catalog) == 28
    assert {item["source_row"] for item in catalog} == set(range(0, 23))
    assert len({item["competition_id"] for item in catalog}) == len(catalog)
    assert len({item["name"] for item in catalog}) == len(catalog)
    assert all(item["category"] in {"A+", "A", "A-"} for item in catalog)
    assert all(set(item["levels"]) <= {"national", "provincial"} for item in catalog)

    row_4 = [item for item in catalog if item["source_row"] == 4]
    row_9 = [item for item in catalog if item["source_row"] == 9]
    assert {item["event_family"] for item in row_4} == {"icpc", "ccpc"}
    assert len(row_9) == 5
    assert not any("、" in item["name"] for item in row_9)
    assert next(item for item in catalog if item["event_family"] == "csp")["source_row"] == 0


def test_formal_policy_options_match_the_source():
    package = load_package()
    assert package["evidence_period"] == {
        "start": "2025-09-01",
        "end": "2028-08-31",
        "boundary": "inclusive",
    }
    assert package["field_schema"]["awards"]["provincial"] == [
        "first_or_above",
        "second",
    ]
    assert package["policy"]["icpc_ccpc"]["invitation_eligible"] is False
    assert package["policy"]["competition_max_count"] == 3
    assert package["policy"]["academic_specialty_cap"] == "15"


def test_catalog_content_digest_is_reviewed_golden_value():
    package = load_package()
    assert canonical_digest({
        "catalog": package["catalog"],
        "evidence_period": package["evidence_period"],
        "field_schema": package["field_schema"],
        "policy": package["policy"],
        "score_matrix": package["score_matrix"],
    }) == "9108688b1c06d70643c8398596300373262707bae92d02324a35745750c7d5d5"
