from conftest import login
from extensions import db
from models import User
from test_ranking_privacy_api import _batch


def test_student_teacher_and_admin_receive_role_trimmed_ranking_dtos(env):
    app, client, users = env
    batch = _batch(env)
    login(client, users["student"])
    student = client.get(f"/api/workflow/rankings/{batch.id}").json
    assert [row["student_id"] for row in student["entries"]] == ["S1"]
    assert student["allowed_actions"] == ["view"]
    login(client, users["admin"])
    admin = client.get(f"/api/workflow/rankings/{batch.id}").json
    assert len(admin["entries"]) == 1
    assert set(admin["allowed_actions"]) >= {"view", "export", "withdraw"}
    login(client, users["other"])
    assert client.get(f"/api/workflow/rankings/{batch.id}").status_code == 403


def test_teacher_cannot_forge_ranking_state_command(env):
    app, client, users = env
    batch = _batch(env)
    with app.app_context():
        teacher = db.session.get(User, users["other"])
        teacher.faculty_id = batch.faculty_id
        db.session.commit()
    login(client, users["other"])
    response = client.post(
        f"/api/workflow/rankings/{batch.id}/commands/withdraw",
        json={"version": batch.version, "reason": "伪造", "idempotency_key": "teacher-withdraw"},
    )
    assert response.status_code == 403
    with app.app_context():
        saved = db.session.get(type(batch), batch.id)
        assert saved.status == "published" and saved.version == 3


def test_ranking_list_filters_by_major_and_year_without_widening_access(env):
    _, client, users = env
    batch = _batch(env)
    scope = {"major_id": batch.major_id, "year": batch.year}
    login(client, users["admin"])
    path = "/api/workflow/rankings"
    assert [item["batch_id"] for item in client.get(path, query_string=scope).json["items"]] == [batch.id]
    assert client.get(path, query_string={**scope, "year": batch.year + 1}).json["items"] == []
    assert client.get(path, query_string={**scope, "major_id": batch.major_id + 1}).json["items"] == []
    assert client.get(path, query_string={**scope, "major_id": "invalid"}).status_code == 400
    login(client, users["other"])
    response = client.get(path, query_string=scope)
    assert response.status_code == 403 or response.json["items"] == []
