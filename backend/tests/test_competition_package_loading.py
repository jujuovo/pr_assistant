import copy
import json
from pathlib import Path

import pytest

from domain.competition_rules import CompetitionPackageError, validate_competition_package
from extensions import db
from models import User
from use_cases.competition_rules import load_current_competition_package
from workflow_models import CompetitionRulePackage


def formal_package():
    path = Path(__file__).parents[1] / "rules" / "competition_2028.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "mutate, expected_detail",
    [
        (lambda value: value["score_matrix"]["national"].pop("third"), "score_matrix.national"),
        (lambda value: value["field_schema"].update(required=[]), "field_schema.required"),
        (lambda value: value["policy"].update(special_ranked_competition_ids=["missing"]), "unknown special"),
        (lambda value: value["catalog"].append(copy.deepcopy(value["catalog"][0])), "duplicated"),
        (lambda value: value["evidence_period"].update(start="2025-09-02"), "evidence period"),
    ],
)
def test_invalid_packages_are_rejected_with_specific_gaps(mutate, expected_detail):
    package = formal_package()
    mutate(package)
    with pytest.raises(CompetitionPackageError) as error:
        validate_competition_package(package)
    assert any(expected_detail in detail for detail in error.value.details)


def test_formal_package_load_is_idempotent(env):
    actor = db.session.get(User, env[2]["admin"])
    snapshot = formal_package()
    first, created = load_current_competition_package(actor, snapshot)
    db.session.commit()
    second, created_again = load_current_competition_package(actor, snapshot)
    assert created is True
    assert created_again is False
    assert first.id == second.id
    assert CompetitionRulePackage.query.filter_by(status="current").count() == 1


def test_different_package_cannot_replace_current_without_correction_flow(env):
    actor = db.session.get(User, env[2]["admin"])
    snapshot = formal_package()
    load_current_competition_package(actor, snapshot)
    db.session.commit()
    changed = formal_package()
    changed["package_id"] = "xmu-se-competition-2028-v2"
    with pytest.raises(CompetitionPackageError) as error:
        load_current_competition_package(actor, changed)
    assert error.value.code == "competition_package_already_current"
