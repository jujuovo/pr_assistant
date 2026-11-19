from extensions import db
from models import Rule, User
from conftest import login
from use_cases.competition_initialization import formal_package_snapshot
from use_cases.competition_rules import load_current_competition_package
from workflow_models import CompetitionRulePackage


def test_old_mutable_rule_endpoint_cannot_change_formal_competition_package(env):
    app, client, users = env
    from blueprints.rule_bp import rule_bp
    app.register_blueprint(rule_bp)
    with app.app_context():
        admin = db.session.get(User, users["admin"])
        package, _ = load_current_competition_package(admin, formal_package_snapshot())
        legacy = Rule(name="旧竞赛规则", type="academic", sub_type="competition",
                      score=5, status="active", faculty_id=admin.faculty_id)
        db.session.add(legacy); db.session.commit()
        package_id, digest, legacy_id = package.id, package.digest, legacy.id
    login(client, users["admin"])
    response = client.put(f"/api/rules/{legacy_id}", json={"score": 99})
    assert response.status_code == 409
    assert response.json["code"] == "competition_package_command_required"
    with app.app_context():
        assert db.session.get(Rule, legacy_id).score == 5
        assert db.session.get(CompetitionRulePackage, package_id).digest == digest


def test_package_list_exposes_source_revision_and_allowed_actions(env):
    app, client, users = env
    from blueprints.rule_bp import rule_bp
    app.register_blueprint(rule_bp)
    with app.app_context():
        admin = db.session.get(User, users["admin"])
        load_current_competition_package(admin, formal_package_snapshot())
        db.session.commit()
    login(client, users["admin"])
    item = client.get("/api/competition-rule-packages").json["items"][0]
    assert {"version", "draft_revision", "status", "source_package_id",
            "created_at", "updated_at", "allowed_actions"} <= item.keys()
