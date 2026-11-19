import copy

from extensions import db
from models import User
from use_cases.competition_initialization import formal_package_snapshot
from use_cases.competition_rules import (
    copy_competition_package_draft, edit_competition_package_draft,
    load_current_competition_package, preview_competition_package_diff,
)
from workflow_models import CompetitionRulePackageRevision


def test_structured_diff_has_stable_catalog_and_policy_paths_and_is_read_only(env):
    app, _client, _users = env
    with app.app_context():
        admin = db.session.get(User, env[2]["admin"])
        source, _ = load_current_competition_package(admin, formal_package_snapshot())
        draft, _ = copy_competition_package_draft(
            admin, source_package_id=source.id, target_cycle=2029,
            idempotency_key="diff-copy",
        )
        candidate = copy.deepcopy(draft.snapshot)
        removed = candidate["catalog"].pop()
        candidate["catalog"].append({**copy.deepcopy(candidate["catalog"][0]),
                                     "competition_id": "new-stable-id",
                                     "competition_name": "新增赛事"})
        candidate["score_matrix"]["national"]["first_or_above"]["A+"] = "9"
        candidate["field_schema"]["required"].append("new_field")
        candidate["policy"]["competition_max_count"] = 4
        edit_competition_package_draft(
            admin, draft, expected_revision=1, snapshot=candidate
        )
        db.session.commit()
        counts_before = {
            "packages": db.session.query(type(draft)).count(),
            "revisions": CompetitionRulePackageRevision.query.count(),
        }
        report = preview_competition_package_diff(admin, draft)
        db.session.rollback()
        paths = {item["path"] for group in ("added", "removed", "changed")
                 for item in report[group]}
        assert "catalog.new-stable-id" in paths
        assert f"catalog.{removed['competition_id']}" in paths
        assert "score_matrix.national.first_or_above.A+" in paths
        assert "field_schema.required" in paths
        assert "policy.competition_max_count" in paths
        assert report["material_impact"] == {"count": 0, "items": []}
        assert report["read_only"] is True
        assert counts_before == {
            "packages": db.session.query(type(draft)).count(),
            "revisions": CompetitionRulePackageRevision.query.count(),
        }
