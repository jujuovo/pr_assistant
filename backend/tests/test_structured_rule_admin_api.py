from conftest import login
from extensions import db
from models import Rule
from workflow_models import RuleVersion


def payload(**changes):
    result = {
        "name": "蓝桥杯省级三等奖", "faculty_id": 1,
        "material_category": "competition", "score": 2,
        "match_terms": {
            "competition_name": "蓝桥杯", "award_level": "三等奖",
            "competition_level": "省级", "region": {"any": True},
            "group": "软件类大学B组", "track": None,
        },
    }
    result.update(changes)
    return result


def register(env):
    from blueprints.rule_bp import rule_bp
    env[0].register_blueprint(rule_bp)


def test_admin_draft_preview_publish_and_disable(env, active_cycle):
    register(env); login(env[1], env[2]["admin"])
    created = env[1].post("/api/structured-rules/drafts", json=payload())
    assert created.status_code == 201, created.json
    rule_id = created.json["id"]
    preview = env[1].post(f"/api/structured-rules/{rule_id}/preview")
    assert preview.status_code == 200 and preview.json["publishable"] is True
    published = env[1].post(
        f"/api/structured-rules/{rule_id}/publish", json={"version": 1}
    )
    assert published.status_code == 200, published.json
    assert published.json["coverage_scan"] == {"available_count": 0, "ambiguous_count": 0}
    assert published.json["rule"]["status"] == "active"
    version = db.session.get(RuleVersion, published.json["rule_version_id"])
    assert version.snapshot["match_terms"]["award_level"] == "三等奖"
    disabled = env[1].post(f"/api/structured-rules/{rule_id}/disable")
    assert disabled.status_code == 200 and disabled.json["status"] == "disabled"


def test_structured_rule_permissions_validation_and_stale_publish(env, active_cycle):
    register(env)
    login(env[1], env[2]["student"])
    assert env[1].post("/api/structured-rules/drafts", json=payload()).status_code == 403
    login(env[1], env[2]["admin"])
    assert env[1].post(
        "/api/structured-rules/drafts", json=payload(faculty_id=2)
    ).status_code == 403
    incomplete = payload()
    incomplete["match_terms"].pop("award_level")
    response = env[1].post("/api/structured-rules/drafts", json=incomplete)
    assert response.status_code == 400 and response.json["code"] == "incomplete_match_terms"

    created = env[1].post("/api/structured-rules/drafts", json=payload()).json
    first = env[1].post(
        f"/api/structured-rules/{created['id']}/publish", json={"version": 1}
    )
    assert first.status_code == 200
    stale = env[1].post(
        f"/api/structured-rules/{created['id']}/publish", json={"version": 1}
    )
    assert stale.status_code == 409 and stale.json["code"] == "source_version_conflict"
    assert RuleVersion.query.filter_by(rule_id=created["id"]).count() == 1
