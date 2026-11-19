from datetime import date

from conftest import login
from extensions import db
from use_cases.cycles import activate_cycle_policy, create_cycle_policy
from models import User


def test_authorized_clients_read_the_same_global_cycle(env):
    app, client, users = env
    with app.app_context():
        admin = db.session.get(User, users["admin"])
        policy, _ = create_cycle_policy(
            admin, 2026, date(2023, 9, 1), date(2026, 8, 31), "2026 推免周期"
        )
        activate_cycle_policy(admin, policy)
        db.session.commit()

    responses = []
    for user_id in (users["student"], users["admin"], users["other"]):
        login(client, user_id)
        response = client.get("/api/workflow/cycles/current")
        assert response.status_code == 200
        responses.append(response.get_json())

    assert responses[0] == responses[1] == responses[2]
    assert responses[0]["cycle_code"] == 2026
    assert responses[0]["policy_version"] == 1
    assert responses[0]["boundary"] == "inclusive"


def test_current_cycle_requires_authentication_and_complete_policy(env):
    app, client, users = env
    assert client.get("/api/workflow/cycles/current").status_code == 401

    login(client, users["student"])
    response = client.get("/api/workflow/cycles/current")
    assert response.status_code == 409
    assert response.get_json()["code"] == "cycle_policy_missing"
