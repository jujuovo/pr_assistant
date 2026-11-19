import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

from extensions import db
from models import Rule
from workflow_models import RuleVersion


def _snapshot(rule):
    return {
        "name": rule.name,
        "type": rule.type,
        "sub_type": rule.sub_type,
        "score": rule.score,
        "max_score": rule.max_score,
        "max_count": rule.max_count,
        "calculation_formula": rule.calculation_formula,
    }


def test_published_rule_snapshot_does_not_follow_rule_edits(env):
    rule = Rule(name="竞赛一等奖", type="academic", sub_type="competition", score=5)
    db.session.add(rule)
    db.session.flush()
    snapshot = _snapshot(rule)
    version = RuleVersion(
        rule_id=rule.id,
        version=1,
        status="published",
        snapshot=snapshot,
        digest=RuleVersion.canonical_digest(snapshot),
    )
    db.session.add(version)
    db.session.commit()

    rule.score = 2
    db.session.commit()
    db.session.refresh(version)
    assert version.snapshot["score"] == 5
    assert version.digest == RuleVersion.canonical_digest(version.snapshot)


def test_published_rule_version_rejects_mutation(env):
    rule = Rule(name="志愿服务", type="comprehensive", score=1)
    db.session.add(rule)
    db.session.flush()
    snapshot = _snapshot(rule)
    version = RuleVersion(
        rule_id=rule.id,
        version=1,
        status="published",
        snapshot=snapshot,
        digest=RuleVersion.canonical_digest(snapshot),
    )
    db.session.add(version)
    db.session.commit()
    version.status = "retired"
    with pytest.raises(ValueError, match="immutable"):
        db.session.commit()
    db.session.rollback()


def test_rule_version_migration_matches_model_and_reverses(env):
    path = Path(__file__).parents[1] / "migrations/versions/20261104_rule_version.py"
    spec = importlib.util.spec_from_file_location("rule_version_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with db.engine.begin() as connection:
        RuleVersion.__table__.drop(connection)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            columns = {column["name"] for column in inspect(connection).get_columns("rule_version")}
            # Structured matching columns belong to later revisions.
            expected = {column.name for column in RuleVersion.__table__.columns}
            expected -= {"match_terms_digest", "match_schema_version"}
            assert columns == expected
            module.downgrade()
            assert not inspect(connection).has_table("rule_version")
            module.upgrade()

