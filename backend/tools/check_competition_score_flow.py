"""Fresh SQLite + real HTTP + production frontend API adapters; no browser automation."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Thread

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def run(output, seed_database=None):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    database = output / 'acceptance.db'
    if database.exists():
        raise ValueError('必须使用新目录，禁止覆盖已有验收或业务数据库')
    if seed_database:
        from tools.check_legacy_application_upgrade import backup_database
        backup_database(seed_database, database)
    os.environ['APP_DATA_ROOT'] = str(output / 'app-data')
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    from tools.prepare_local import main
    main(database)
    from app import app
    from extensions import db
    from models import Student, User
    from sqlalchemy import inspect
    from workflow_models import FacultyScoringPolicy, ScoreEntry
    from material_models import MaterialRecord
    from werkzeug.serving import make_server
    from services.competition_ocr.worker import run_one_ocr
    from services.recognition.provider import PaddleProvider

    app.config.update(TESTING=True)
    cookies, students = {}, {}
    with app.app_context():
        assert not inspect(db.engine).has_table("application")
        initial_materials = MaterialRecord.query.count()
        initial_scores = ScoreEntry.query.filter_by(status="active").count()
        template = Student.query.filter_by(student_id='student001').one()
        teacher = User.query.filter_by(username='teacher001').one()
        scope = dict(faculty_id=template.faculty_id, department_id=template.department_id,
                     major_id=template.major_id)
        roles = ['student' + str(i) for i in range(25)] + ['aggregate', 'duplicate', 'cap', 'ocr', 'work']
        accounts = {'teacher': teacher}
        for i, role in enumerate(roles):
            number = ('cutover' if seed_database else 'mapping') + str(i).zfill(2)
            student = Student(student_id=number, student_name='隔离验收' + str(i),
                              academic_score=76, gpa=3.8, **scope)
            user = User(username=number, name=student.student_name, password='unused-test-only',
                        role='student', student_id=number, status='active', **scope)
            db.session.add_all([student, user])
            accounts[role], students[role] = user, number
        db.session.commit()
        for role, user in accounts.items():
            client = app.test_client()
            with client.session_transaction() as session:
                session['user_id'] = user.id
            cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
            cookies[role] = app.config['SESSION_COOKIE_NAME'] + '=' + cookie.value
        published = FacultyScoringPolicy.query.filter_by(
            faculty_id=template.faculty_id, cycle_code=2028, status="published").count() > 0
        assert published or seed_database, "新库应具备已发布的演示政策"
        ids = dict(faculty=template.faculty_id, department=template.department_id,
                   major=template.major_id, publishedPolicy=published)

    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = dict(base='http://127.0.0.1:' + str(server.server_port), cookies=cookies,
                  students=students, sample=str(BACKEND / 'samples/LanqiaoCup/example5.jpg'), **ids)
    script = BACKEND.parent / 'frontend/tools/check_competition_score_flow.mjs'

    def node(phase, **extra):
        result = subprocess.run(['node', str(script)], input=json.dumps(dict(config, phase=phase, **extra)),
                                text=True, encoding='utf-8', capture_output=True, timeout=180)
        if result.returncode:
            raise RuntimeError(result.stderr[-6000:] + '\n' + result.stdout[-2000:])
        return json.loads(result.stdout)

    try:
        print('Running frontend adapters against isolated live HTTP backend...', flush=True)
        matrix = node('matrix')
        print('Mapping matrix and aggregation passed; starting real Lanqiao OCR...', flush=True)
        (output / 'matrix.json').write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding='utf-8')
        with app.app_context():
            assert run_one_ocr(app, PaddleProvider())
        ocr = node('ocr', record=matrix['queued'])
        with app.app_context():
            assert not inspect(db.engine).has_table("application")
            assert MaterialRecord.query.count() - initial_materials == 36
            assert ScoreEntry.query.filter_by(status="active").count() - initial_scores == 36
            from hashlib import sha256
            from services.materials.service import stored_path
            from workflow_models import RankingEntry
            reviewed = db.session.get(MaterialRecord, matrix["queued"]["id"])
            original = reviewed.attachments[0]
            admin = User.query.filter_by(role="admin", faculty_id=ids["faculty"]).first()
            assert admin is not None
            client = app.test_client()
            with client.session_transaction() as login:
                login["user_id"] = admin.id
            rank = client.post("/api/workflow/rankings/generate", json={
                "year": 2028, "faculty_id": ids["faculty"], "major_id": ids["major"],
                "cutoff_at": "2030-01-01T00:00:00", "idempotency_key": "schema-acceptance-ranking"})
            assert rank.status_code == 201, rank.json
            ranked = RankingEntry.query.filter_by(student_id=students["ocr"]).order_by(RankingEntry.id.desc()).first()
            assert ranked is not None and ranked.rank is not None
            student_user = User.query.filter_by(student_id=students["ocr"]).one()
            for route, identifier in (("users", student_user.id), ("faculties", ids["faculty"]),
                                      ("departments", ids["department"]), ("majors", ids["major"])):
                protected = client.delete(f"/api/admin/{route}/{identifier}")
                assert protected.status_code == 409, (route, protected.status_code, protected.json)
            assert sha256(stored_path(original.stored_name).read_bytes()).hexdigest() == original.sha256
            counts = dict(materials=MaterialRecord.query.count(), active_scores=ScoreEntry.query.filter_by(status='active').count(),
                          legacy_table_present=False, ocr_student_rank=ranked.rank, protected_deletions=4)
        result = dict(database=str(database), matrix=matrix, real_ocr=ocr, counts=counts,
                      frontend_adapters='production modules imported directly, actual HTTP',
                      authentication='isolated server sessions; login/captcha UI not covered', browser_verified=False)
        (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print('PASSED: 25 award/team mappings, top-three, deduplication, cap, report and real OCR.')
        print('Evidence:', output / 'result.json')
    finally:
        server.shutdown()
        thread.join(timeout=10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=BACKEND / 'outputs' /
                        ('score-flow-' + datetime.now().strftime('%Y%m%d-%H%M%S')))
    parser.add_argument("--seed-database", type=Path, help="可选，只读复制已升级的验收源库")
    args = parser.parse_args()
    run(args.output, args.seed_database)
