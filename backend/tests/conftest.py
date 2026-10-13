import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from flask import Flask
from extensions import db
from models import Faculty, Department, Major, Student, User
from blueprints.automation_bp import automation_bp
from blueprints.application_bp import application_bp
from blueprints.certificate_bp import certificate_bp


@pytest.fixture
def env(tmp_path):
    app = Flask("automation_test")
    app.config.update(TESTING=True, SECRET_KEY="test", SQLALCHEMY_DATABASE_URI="sqlite://",
                      AUTOMATION_UPLOAD_FOLDER=str(tmp_path / "images"), AUTOMATION_MAX_FILES=30,
                      AUTOMATION_MAX_IMAGE_BYTES=1024*1024, AUTOMATION_MAX_PIXELS=20_000_000,
                      AUTOMATION_LEASE_SECONDS=60, AUTOMATION_MAX_ATTEMPTS=3)
    db.init_app(app)
    app.register_blueprint(automation_bp)
    app.register_blueprint(application_bp)
    app.register_blueprint(certificate_bp)
    from blueprints.material_bp import material_bp
    app.register_blueprint(material_bp)
    app.config['MATERIAL_STORAGE_FOLDER'] = str(tmp_path / 'evidence')
    app.config['CERTIFICATE_STORAGE_FOLDER'] = str(tmp_path / 'certificates')
    app.config['FILE_FOLDER'] = str(tmp_path / 'uploads' / 'files')
    app.config['UPLOAD_FOLDER'] = str(tmp_path / 'uploads')
    with app.app_context():
        db.create_all()
        faculty = Faculty(name="测试学院")
        faculty2 = Faculty(name="其他学院")
        db.session.add_all([faculty, faculty2])
        db.session.flush()
        department = Department(name="测试系", faculty_id=faculty.id)
        db.session.add(department)
        db.session.flush()
        major = Major(name="测试专业", department_id=department.id)
        db.session.add(major)
        db.session.flush()
        student = Student(student_id="S1", student_name="张三", faculty_id=faculty.id,
                          department_id=department.id, major_id=major.id, academic_score=80)
        db.session.add(student)
        db.session.flush()
        users = [User(username="student", name="张三", password="test", role="student", status="active",
                      student_id="S1", faculty_id=faculty.id, department_id=department.id, major_id=major.id),
                 User(username="admin", name="管理员", password="test", role="admin", status="active", faculty_id=faculty.id),
                 User(username="other", name="外院审核", password="test", role="teacher", status="active", faculty_id=faculty2.id)]
        db.session.add_all(users)
        db.session.commit()
        yield app, app.test_client(), {u.username: u.id for u in users}
        db.session.remove()
        db.drop_all()


def login(client, user_id):
    with client.session_transaction() as state:
        state["user_id"] = user_id
