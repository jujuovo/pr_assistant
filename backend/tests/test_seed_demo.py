import pytest
from datetime import date
from types import SimpleNamespace
from models import User, Student, Faculty, Department, Major
from extensions import db
from tools.seed_demo import seed_demo


def test_seed_repeat_preserves_password_scores_and_relations(env):
    first = seed_demo()
    assert all(r['action'] == 'created' for r in first)
    users = [User.query.filter_by(username=n).one() for n in ('student001','teacher001','admin001')]
    assert all(u.check_password('demo123') for u in users)
    assert len({u.faculty_id for u in users}) == 1
    assert Faculty.query.filter_by(id=users[0].faculty_id).one().name == '信息学院'
    assert Department.query.filter_by(id=users[0].department_id).one().name == '计算机系'
    assert Major.query.filter_by(id=users[0].major_id).one().name == '软件工程专业'
    assert users[1].student_id is None and users[2].student_id is None
    student = Student.query.filter_by(student_id='student001').one()
    assert student.cet6_score == 550 and student.gpa == 3.8
    counts = (User.query.count(), Student.query.count(), Faculty.query.count())
    users[0].set_password('changed-for-test')
    student.academic_score = 90
    db.session.commit()
    seed_demo()
    assert (User.query.count(), Student.query.count(), Faculty.query.count()) == counts
    assert users[0].check_password('changed-for-test') and student.academic_score == 90
    seed_demo(reset_password=True)
    assert users[0].check_password('demo123')


def test_seed_collision_rolls_back(env):
    user = User(username='teacher001', name='Existing user', role='admin', status='active')
    user.set_password('untouched')
    db.session.add(user); db.session.commit()
    with pytest.raises(ValueError, match='teacher001'):
        seed_demo()
    assert Student.query.filter_by(student_id='student001').first() is None
    assert Faculty.query.filter_by(name='信息学院').first() is None
    assert user.name == 'Existing user' and user.check_password('untouched')


def test_optional_rule_is_faculty_scoped_and_idempotent(env):
    from models import Rule, RuleCalculation
    from workflow_models import RecommendationCyclePolicy, RuleVersion
    seed_demo(with_test_rule=True)
    faculty = Faculty.query.filter_by(name='信息学院').one()
    rule = Rule.query.filter_by(faculty_id=faculty.id).one()
    assert rule.score == 5 and rule.max_score == 10 and rule.max_count == 5
    calculation = RuleCalculation.query.filter_by(rule_id=rule.id).one()
    assert [n['score'] for n in calculation.parameters['tree']['root']['children']] == [5, 3]
    policy = RecommendationCyclePolicy.query.filter_by(active_marker=1).one()
    version = RuleVersion.query.filter_by(rule_id=rule.id).one()
    assert policy.cycle_code == 2026
    assert policy.eligible_award_start_date.isoformat() == '2023-09-01'
    assert policy.eligible_award_end_date.isoformat() == '2026-08-31'
    assert version.snapshot['cycle_code'] == 2026
    assert version.snapshot['score'] == 5
    rule.score = 4
    db.session.commit()
    seed_demo(with_test_rule=True)
    assert Rule.query.filter_by(faculty_id=faculty.id).count() == 1
    assert RuleCalculation.query.filter_by(rule_id=rule.id).count() == 1
    assert rule.score == 4
    assert RuleVersion.query.filter_by(rule_id=rule.id).count() == 2
    seed_demo(with_test_rule=True)
    assert RuleVersion.query.filter_by(rule_id=rule.id).count() == 2
    assert RecommendationCyclePolicy.query.count() == 1


def test_shared_settings_use_absolute_dates_and_keep_other_fields(env):
    from models import SystemSettings
    from datetime import datetime
    settings = SystemSettings(academic_year='2024', single_file_size_limit=17, system_status='maintenance')
    db.session.add(settings); db.session.commit()
    seed_demo(with_test_rule=True, with_test_settings=True)
    seed_demo(with_test_rule=True, with_test_settings=True)
    assert settings.academic_year == '2026'
    assert settings.application_start == datetime(2026, 10, 1, 10, 28, 46, 965115)
    assert settings.application_end.year == 2027
    assert settings.single_file_size_limit == 17 and settings.system_status == 'maintenance'


def test_student001_lanqiao_prerequisites_resolve_to_five_points(env):
    from domain.cycles import evaluate_award_date
    from domain.scoring import calculate_score
    from workflow_models import RecommendationCyclePolicy
    from use_cases.scoring import match_published_rule

    seed_demo(with_test_rule=True, with_test_settings=True)
    student = Student.query.filter_by(student_id='student001').one()
    policy = RecommendationCyclePolicy.query.filter_by(active_marker=1).one()
    eligibility = evaluate_award_date(
        date(2024, 5, 1),
        policy.eligible_award_start_date,
        policy.eligible_award_end_date,
    )
    match = match_published_rule(SimpleNamespace(
        year=policy.cycle_code,
        category='competition',
        faculty_id=student.faculty_id,
    ))

    assert eligibility.eligible is True
    assert match['status'] == 'matched'
    assert calculate_score(match['version'].snapshot).effective_score == 5
