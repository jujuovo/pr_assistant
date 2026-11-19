from models import Student
from conftest import login


DERIVED = {
    "comprehensive_score": 999,
    "academic_specialty_total": 999,
    "comprehensive_performance_total": 999,
    "major_ranking": 1,
    "total_students": 1,
}


def test_student_teacher_and_admin_cannot_forge_derived_student_fields(env):
    app, client, users = env
    from blueprints.score_bp import score_bp
    app.register_blueprint(score_bp)
    with app.app_context():
        student = Student.query.filter_by(student_id="S1").one()
        student.comprehensive_score = 81
        student.academic_specialty_total = 4
        student.comprehensive_performance_total = 2
        student.major_ranking = 7
        student.total_students = 40
        from extensions import db
        db.session.commit()
        database_id = student.id

    for username, expected in (("student", 403), ("other", 403), ("admin", 400)):
        login(client, users[username])
        response = client.put(f"/api/students/{database_id}", json=DERIVED)
        assert response.status_code == expected
        if username == "admin":
            assert response.json["code"] == "derived_fields_read_only"

    with app.app_context():
        student = Student.query.filter_by(student_id="S1").one()
        assert (student.comprehensive_score, student.academic_specialty_total,
                student.comprehensive_performance_total, student.major_ranking,
                student.total_students) == (81, 4, 2, 7, 40)


def test_material_contract_rejects_derived_fields_without_creating_record(env, active_cycle):
    app, client, users = env
    login(client, users["student"])
    response = client.post("/api/materials/honor/records", json={
        "year": active_cycle.cycle_code,
        "data": {"project_name": "测试荣誉", "award_date": "2026-01-01",
                 "comprehensive_score": 999},
    })
    assert response.status_code == 400
    assert response.json["code"] == "derived_fields_read_only"
    with app.app_context():
        from material_models import MaterialRecord
        assert MaterialRecord.query.count() == 0
