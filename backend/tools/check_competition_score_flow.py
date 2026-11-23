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


def run(output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    database = output / 'acceptance.db'
    if database.exists():
        raise ValueError('必须使用新目录，禁止覆盖已有验收或业务数据库')
    os.environ['APP_DATA_ROOT'] = str(output / 'app-data')
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    from tools.prepare_local import main
    main(database)
    from app import app
    from extensions import db
    from models import Application, Student, User
    from workflow_models import ScoreEntry
    from material_models import MaterialRecord
    from werkzeug.serving import make_server
    from services.competition_ocr.worker import run_one_ocr
    from services.recognition.provider import PaddleProvider

    app.config.update(TESTING=True)
    cookies, students = {}, {}
    with app.app_context():
        template = Student.query.filter_by(student_id='student001').one()
        teacher = User.query.filter_by(username='teacher001').one()
        scope = dict(faculty_id=template.faculty_id, department_id=template.department_id,
                     major_id=template.major_id)
        roles = ['student' + str(i) for i in range(25)] + ['aggregate', 'duplicate', 'cap', 'ocr', 'work']
        accounts = {'teacher': teacher}
        for i, role in enumerate(roles):
            number = 'mapping' + str(i).zfill(2)
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
        ids = dict(faculty=template.faculty_id, department=template.department_id, major=template.major_id)

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
            assert Application.query.count() == 0
            assert MaterialRecord.query.count() == ScoreEntry.query.filter_by(status='active').count() == 36
            counts = dict(materials=MaterialRecord.query.count(), active_scores=ScoreEntry.query.filter_by(status='active').count(),
                          legacy_applications=Application.query.count())
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
    run(parser.parse_args().output)
