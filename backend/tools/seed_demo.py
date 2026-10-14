"""Shared Windows/macOS development seed. Only writes an explicitly selected SQLite copy."""
import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask import Flask
from sqlalchemy import inspect
from extensions import db
from models import Faculty, Department, Major, Student, User, Rule, RuleCalculation, SystemSettings

CONFIG = json.loads((Path(__file__).resolve().parents[1] / 'seed/demo.json').read_text(encoding='utf-8'))


def seed_demo(reset_password=False, with_test_rule=False, with_test_settings=False):
    """One transaction; repeats preserve existing passwords, scores and business records."""
    try:
        required = {'faculty', 'department', 'major', 'student', 'user'}
        if not required.issubset(set(inspect(db.engine).get_table_names())):
            raise ValueError('数据库表尚未准备，请先执行本地数据库准备或迁移')
        faculty = Faculty.query.filter_by(name=CONFIG['organization']['faculty']).one_or_none()
        if faculty is None:
            faculty = Faculty(name=CONFIG['organization']['faculty'], description='开发测试学院')
            db.session.add(faculty)
            db.session.flush()
        department = Department.query.filter_by(name=CONFIG['organization']['department'], faculty_id=faculty.id).one_or_none()
        if department is None:
            department = Department(name=CONFIG['organization']['department'], faculty_id=faculty.id)
            db.session.add(department)
            db.session.flush()
        major = Major.query.filter_by(name=CONFIG['organization']['major'], department_id=department.id).one_or_none()
        if major is None:
            major = Major(name=CONFIG['organization']['major'], department_id=department.id)
            db.session.add(major)
            db.session.flush()
        org = dict(faculty_id=faculty.id, department_id=department.id, major_id=major.id)
        student = Student.query.filter_by(student_id=CONFIG['student']['student_id']).one_or_none()
        if student is None:
            student = Student(**CONFIG['student'], **org)
            db.session.add(student)
            db.session.flush()
        elif student.student_name != CONFIG['student']['student_name'] or any(getattr(student, k) != v for k, v in org.items()):
            raise ValueError('student001 学生记录与目标资料不一致，已停止；不会覆盖已有学生')
        linked = User.query.filter_by(student_id=CONFIG['student']['student_id']).one_or_none()
        if linked and linked.username != next(a['username'] for a in CONFIG['accounts'] if a['role'] == 'student'):
            raise ValueError('测试学号已绑定其他账号，已停止')
        result = []
        for account in CONFIG['accounts']:
            username, role, name = account['username'], account['role'], account['name']
            user = User.query.filter_by(username=username).one_or_none()
            created = user is None
            if created:
                user = User(username=username, role=role, name=name, status='active',
                            student_id=CONFIG['student']['student_id'] if role == 'student' else None,
                            email=account['email'], phone=account['phone'], **org)
                user.set_password(account['password'])
                db.session.add(user)
            else:
                expected = dict(role=role, name=name, status='active',
                                student_id=CONFIG['student']['student_id'] if role == 'student' else None, **org)
                if any(getattr(user, key) != value for key, value in expected.items()):
                    raise ValueError(f'{username} 已存在且资料不一致，已停止；不会覆盖现有账号')
                if reset_password:
                    user.set_password(account['password'])
            result.append({'username': username, 'role': role,
                           'action': 'created' if created else 'password_reset' if reset_password else 'preserved'})
        if with_test_rule:
            spec = CONFIG['rule']
            rule = Rule.query.filter_by(faculty_id=faculty.id, name=spec['name']).one_or_none()
            if rule is None:
                rule = Rule(**{k: v for k, v in spec.items() if k != 'parameters'},
                            faculty_id=faculty.id, calculation_formula=spec['parameters'])
                db.session.add(rule)
                db.session.flush()
                db.session.add(RuleCalculation(rule_id=rule.id, calculation_type='tree',
                    parameters=spec['parameters'], max_score=spec['max_score'], precision=2, status='active'))
        if with_test_settings:
            settings = SystemSettings.query.one_or_none()
            if settings is None:
                settings = SystemSettings()
                db.session.add(settings)
            for key, value in CONFIG['system_settings'].items():
                setattr(settings, key, datetime.fromisoformat(value) if key in ('application_start', 'application_end') else value)
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description='创建三角色开发账号；可选竞赛测试规则，不创建志愿政策或伪造审核成绩')
    parser.add_argument('--database-file', required=True, type=Path, help='已准备好的本地 SQLite 测试副本')
    parser.add_argument('--all', action='store_true', help='加载共享账号、信息学院测试规则及固定日期设置')
    parser.add_argument('--with-test-settings', action='store_true', help='应用共享配置中的固定年度/日期，保留其他设置')
    parser.add_argument('--with-test-rule', action='store_true', help='仅为信息学院补建竞赛测试规则，不覆盖已有同名规则')
    parser.add_argument('--reset-password', action='store_true', help='明确将这三个测试账号密码恢复为 demo123')
    args = parser.parse_args()
    path = args.database_file.expanduser().resolve()
    source = Path(__file__).resolve().parents[1] / 'instance/gradpush.db'
    if path == source.resolve():
        parser.error('不能直接修改仓库附带源库，请指定本地测试副本')
    if not path.is_file():
        parser.error('测试数据库不存在，请先准备数据库')
    app = Flask('development_seed')
    from sqlalchemy import URL
    app.config['SQLALCHEMY_DATABASE_URI'] = URL.create('sqlite', database=str(path))
    db.init_app(app)
    with app.app_context():
        result = seed_demo(args.reset_password, args.with_test_rule or args.all, args.with_test_settings or args.all)
    print(f'开发测试数据库：{path}')
    for item in result:
        print(f"{item['username']} ({item['role']}): {item['action']}")
    print('新建账号密码为 demo123；已存在账号的密码默认不变。验证码使用真实登录页显示的值。')


if __name__ == '__main__':
    main()
