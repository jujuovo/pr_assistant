import importlib.util
import json
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect
from sqlalchemy.exc import IntegrityError

from extensions import db
from material_models import MaterialRecord
from workflow_models import CompetitionRulePackage


def formal_snapshot():
    path = Path(__file__).parents[1] / "rules" / "competition_2028.json"
    return json.loads(path.read_text(encoding="utf-8"))


def make_package(actor_id, *, package_id="formal-v1", version=1, status="current"):
    snapshot = formal_snapshot()
    return CompetitionRulePackage(
        package_id=package_id,
        cycle_code=2028,
        scope_key="global",
        version=version,
        status=status,
        snapshot=snapshot,
        digest=CompetitionRulePackage.canonical_digest(snapshot),
        current_scope_key=(
            CompetitionRulePackage.current_key(2028) if status == "current" else None
        ),
        created_by=actor_id,
        published_by=actor_id if status == "current" else None,
    )


def test_only_one_current_package_is_allowed_per_cycle_and_scope(env):
    actor_id = env[2]["admin"]
    db.session.add(make_package(actor_id))
    db.session.commit()
    second = make_package(actor_id, package_id="formal-v2", version=2)
    second.digest = "f" * 64
    db.session.add(second)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_published_package_snapshot_is_immutable_and_historical_snapshot_readable(env):
    package = make_package(env[2]["admin"])
    db.session.add(package)
    db.session.commit()
    package.snapshot = {"tampered": True}
    with pytest.raises(ValueError, match="immutable"):
        db.session.commit()
    db.session.rollback()
    stored = db.session.get(CompetitionRulePackage, package.id)
    assert stored.snapshot["package_id"] == "xmu-se-competition-2028-v1"
    assert len(stored.snapshot["catalog"]) == 28


def test_material_can_bind_the_exact_package_snapshot(env):
    package = make_package(env[2]["admin"])
    db.session.add(package)
    db.session.flush()
    material = MaterialRecord(
        student_id="S1", faculty_id=1, category="competition", year=2028,
        status="draft", data={}, analysis={}, competition_rule_package_id=package.id,
    )
    db.session.add(material)
    db.session.commit()
    assert db.session.get(MaterialRecord, material.id).competition_rule_package_id == package.id


def test_competition_package_migration_upgrades_and_downgrades():
    path = Path(__file__).parents[1] / "migrations/versions/20261109_competition_rule_package.py"
    spec = importlib.util.spec_from_file_location("competition_package_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    baseline = MetaData()
    Table("user", baseline, Column("id", Integer, primary_key=True))
    Table(
        "material_record", baseline,
        Column("id", Integer, primary_key=True),
        Column("status", String(32), nullable=False),
    )
    baseline.create_all(engine)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            columns = {
                column["name"]
                for column in inspect(connection).get_columns("competition_rule_package")
            }
            later_draft_columns = {
                "draft_revision", "source_package_id", "source_digest",
                "source_summary", "updated_by", "updated_at",
            }
            expected_base_columns = {
                column.name for column in CompetitionRulePackage.__table__.columns
            } - later_draft_columns
            assert columns == expected_base_columns
            material_columns = {
                column["name"]
                for column in inspect(connection).get_columns("material_record")
            }
            assert "competition_rule_package_id" in material_columns
            module.downgrade()
            assert not inspect(connection).has_table("competition_rule_package")
            material_columns = {
                column["name"]
                for column in inspect(connection).get_columns("material_record")
            }
            assert "competition_rule_package_id" not in material_columns
