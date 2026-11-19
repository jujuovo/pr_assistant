from extensions import db
from material_models import MaterialRecord
from models import Rule, Student
from use_cases.migration import legacy_reconciliation_report
from workflow_models import RuleVersion


THIRD = {"competition_name": "蓝桥杯", "award_level": "三等奖",
         "competition_level": "省级", "region": "福建赛区",
         "group": "软件类大学B组", "track": None, "award_date": "2026-05-08"}


def published(name, award_level):
    rule = Rule(name=name, type="academic", sub_type="competition", score=5,
                status="active", faculty_id=1)
    db.session.add(rule); db.session.flush()
    terms = {key: THIRD[key] for key in (
        "competition_name", "award_level", "competition_level", "region", "group", "track"
    )}
    terms["award_level"] = award_level
    snapshot = {"name": name, "sub_type": "competition", "faculty_id": 1,
                "cycle_code": 2026, "score": 5, "match_terms": terms,
                "match_schema_version": "material-terms-v1"}
    item = RuleVersion(rule_id=rule.id, version=1, status="published", snapshot=snapshot,
                       digest=RuleVersion.canonical_digest(snapshot),
                       match_terms_digest=name, match_schema_version="material-terms-v1")
    db.session.add(item); db.session.flush(); return item


def material(**changes):
    values = dict(student_id="S1", faculty_id=1, category="competition", year=2026,
                  status="draft", data={"award_date": "2026-05-08"}, analysis={},
                  confirmed_terms=THIRD, normalized_terms=THIRD,
                  normalization_version="material-terms-v1")
    values.update(changes)
    row = MaterialRecord(**values); db.session.add(row); return row


def test_structured_reconciliation_is_stable_read_only_and_reports_ranking_scope(env):
    first_prize = published("一等奖默认规则", "一等奖")
    published("三等奖规则一", "三等奖")
    published("三等奖规则二", "三等奖")
    material(status="rule_unmatched")
    material(data={"award_date": "2026-11-12"})
    material(confirmed_terms=None, normalized_terms=None)
    material(rule_version_id=first_prize.id)
    db.session.commit()
    before = {table.name: db.session.query(table).count() for table in db.metadata.sorted_tables}
    first = legacy_reconciliation_report(2026, faculty_id=1)
    second = legacy_reconciliation_report(2026, faculty_id=1)
    after = {table.name: db.session.query(table).count() for table in db.metadata.sorted_tables}
    assert first == second and before == after
    counts = first["issue_counts"]
    assert counts["evidence_date_conflict"] >= 1
    assert counts["missing_confirmation_snapshot"] >= 1
    assert counts["uncovered_structured_terms"] >= 1
    assert counts["ambiguous_structured_rules"] >= 1
    assert counts["incorrect_default_rule"] >= 1
    assert first["ranking_release_allowed"] is False
    assert all(item["affected_ranking_scope"]["faculty_id"] == 1
               for item in first["material_issues"])
