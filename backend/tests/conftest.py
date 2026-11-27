import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 测试环境默认关闭 SQLite 外键：多处用例刻意构造孤儿数据来验证容错路径
# （例如「报告坏学生时不能声称完成」）。生产与本地开发默认开启，见 extensions.py。
# 需要用外键跑整套测试时：$env:SQLITE_FOREIGN_KEYS='1'; pytest
os.environ.setdefault("SQLITE_FOREIGN_KEYS", "0")

import pytest
from datetime import date
from flask import Flask
from extensions import db
from models import Faculty, Department, Major, Student, User
from blueprints.application_bp import application_bp
from blueprints.certificate_bp import certificate_bp
from blueprints.workflow_bp import workflow_bp


def prepare_final_stage():
    """Fixture for existing tests of final review, OCR gates and score formulas.

    No versions or audit events change. Full stage transitions are exercised by
    test_staged_material_review, rather than repeated in every scoring test.
    """
    from material_models import MaterialRecord
    from models import Application
    MaterialRecord.query.filter(MaterialRecord.status.in_(['submitted', 'under_review'])).update(
        {'review_stage': 3}, synchronize_session='fetch')
    Application.query.filter_by(status='pending').update({'review_stage': 3}, synchronize_session='fetch')
    db.session.commit()


def approve_pending_preliminaries(client):
    """Exercise both pre-review APIs before existing category scoring journeys."""
    from material_models import MaterialRecord
    from workflow_models import ScoreEntry, StudentScoreSnapshot
    pending = MaterialRecord.query.filter(MaterialRecord.status.in_(['submitted', 'under_review']),
                                          MaterialRecord.review_stage < 3).all()
    for row in pending:
        before = ScoreEntry.query.count()
        snapshots_before = StudentScoreSnapshot.query.count()
        for stage in range(row.review_stage, 3):
            role = f'reviewer_level{stage}'
            username = f'journey-{role}-{row.faculty_id}'
            user = User.query.filter_by(username=username).first()
            if user is None:
                user = User(username=username, name=role, password='test', role=role,
                            faculty_id=row.faculty_id, status='active')
                db.session.add(user)
                db.session.commit()
            login(client, user.id)
            response = client.post(f'/api/materials/{row.category}/records/{row.id}/review', json={
                'version': row.version, 'decision': 'approve' if row.category == 'competition' else 'verified',
                'comment': '预审核对证明', 'idempotency_key': f'preliminary:{row.id}:{stage}:{row.version}',
            })
            assert response.status_code == 200, response.json
            db.session.refresh(row)
            assert row.review_stage == stage + 1 and row.status == 'submitted'
            assert ScoreEntry.query.count() == before
            assert StudentScoreSnapshot.query.count() == snapshots_before


@pytest.fixture
def env(tmp_path):
    app = Flask("automation_test")
    app.config.update(TESTING=True, SECRET_KEY="test", SQLALCHEMY_DATABASE_URI="sqlite://",
                      AUTOMATION_UPLOAD_FOLDER=str(tmp_path / "images"), AUTOMATION_MAX_FILES=30,
                      AUTOMATION_MAX_IMAGE_BYTES=1024*1024, AUTOMATION_MAX_PIXELS=20_000_000,
                      AUTOMATION_LEASE_SECONDS=60, AUTOMATION_MAX_ATTEMPTS=3,
                      ALLOW_LEGACY_CERTIFICATE_PREVIEWS=True)
    db.init_app(app)
    app.register_blueprint(application_bp)
    app.register_blueprint(certificate_bp)
    from blueprints.ocr_bp import ocr_bp
    app.register_blueprint(ocr_bp)
    app.config['OCR_STORAGE_FOLDER'] = str(tmp_path / 'ocr-jobs')
    app.register_blueprint(workflow_bp)
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


@pytest.fixture
def active_cycle(env):
    from use_cases.cycles import activate_cycle_policy, create_cycle_policy

    admin = db.session.get(User, env[2]["admin"])
    policy, _ = create_cycle_policy(
        admin, 2026, date(2023, 9, 1), date(2026, 8, 31), "2026 推免周期"
    )
    activate_cycle_policy(admin, policy)
    db.session.commit()
    return policy


@pytest.fixture
def active_honor_rule(env, active_cycle):
    from models import Rule
    from use_cases.rule_versions import publish_rule_version

    admin = db.session.get(User, env[2]["admin"])
    rule = Rule(
        name="荣誉称号测试规则", type="academic", sub_type="honor",
        score=1, max_score=1, faculty_id=admin.faculty_id, status="active",
    )
    db.session.add(rule)
    publish_rule_version(rule, published_by=admin, cycle_code=active_cycle.cycle_code)
    db.session.commit()
    return rule


@pytest.fixture
def active_cycle_2025(env):
    from use_cases.cycles import activate_cycle_policy, create_cycle_policy

    admin = db.session.get(User, env[2]["admin"])
    policy, _ = create_cycle_policy(
        admin, 2025, date(2023, 1, 1), date(2025, 12, 31), "2025 推免周期"
    )
    activate_cycle_policy(admin, policy)
    db.session.commit()
    return policy
