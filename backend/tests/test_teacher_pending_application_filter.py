from conftest import login
from extensions import db
from material_models import MaterialRecord
from legacy_models import Application
from models import Student, User
from test_material_rule_submission import MATERIAL_TERMS, version


def application(student, name):
    row = Application(student_id=student.student_id, student_name=student.student_name,
                      faculty_id=student.faculty_id, department_id=student.department_id,
                      major_id=student.major_id, application_type="academic",
                      project_name=name, status="pending", self_score=0)
    db.session.add(row); db.session.flush()
    return row


def material(app, status, rule_version_id=None):
    row = MaterialRecord(student_id=app.student_id, faculty_id=app.faculty_id,
                         application_id=app.id, category="competition", year=2026,
                         status=status, rule_version_id=rule_version_id,
                         data={}, analysis={}, normalized_terms=MATERIAL_TERMS)
    db.session.add(row); return row


def test_teacher_pending_application_projection_excludes_unmatched_and_available(env, active_cycle):
    student = Student.query.filter_by(student_id="S1").one()
    teacher = User(username="projection-teacher", name="教师", password="test",
                   role="teacher", status="active", faculty_id=1)
    db.session.add(teacher)
    published = version(1)
    legacy = application(student, "兼容旧申请")
    unmatched = application(student, "无规则"); material(unmatched, "rule_unmatched")
    available = application(student, "待学生确认"); material(available, "rule_available")
    submitted = application(student, "正式提交"); material(submitted, "submitted", published.id)
    db.session.commit(); login(env[1], teacher.id)
    response = env[1].get("/api/applications/pending")
    assert response.status_code == 200
    names = {item["projectName"] for item in response.json}
    assert names == {legacy.project_name, submitted.project_name}
