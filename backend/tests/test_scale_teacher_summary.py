"""Home counters must cover the same research queues as the review workbench."""
from conftest import login
from extensions import db
from material_models import MaterialRecord
from models import User


def test_teacher_summary_counts_research_innovation_and_preserves_faculty_scope(env):
    reviewer = User(username='scale-reviewer', name='Scale reviewer', role='teacher',
                    status='active', faculty_id=1, password='test')
    db.session.add(reviewer)
    for category in ('research_paper', 'invention_patent', 'innovation_training'):
        for status in ('submitted', 'needs_correction', 'scored'):
            db.session.add(MaterialRecord(student_id='S1', faculty_id=1, category=category,
                                          year=2026, status=status, review_stage=3, data={}, analysis={}))
    db.session.add(MaterialRecord(student_id='S1', faculty_id=2, category='research_paper',
                                 year=2026, status='submitted', review_stage=3, data={}, analysis={}))
    db.session.commit()
    login(env[1], reviewer.id)
    response=env[1].get('/api/materials/teacher/summary')
    assert response.status_code==200
    assert response.json['pending_count']==3
    assert response.json['needs_correction_count']==3
    assert response.json['completed_count']==3


def test_competition_workbench_pages_pending_separately_from_newer_drafts(env):
    from test_ocr_workflow_integration import setup_formal
    from workflow_models import CompetitionRulePackage
    setup_formal(env)
    reviewer=User(username='queue-reviewer',name='Queue reviewer',role='teacher',status='active',faculty_id=1,password='test')
    db.session.add(reviewer)
    package=CompetitionRulePackage.query.filter_by(status='current',cycle_code=2028).one()
    for status,count in [('submitted',70),('draft',60),('scored',65)]:
        for i in range(count):
            db.session.add(MaterialRecord(student_id='S1',faculty_id=1,category='competition',year=2028,
                status=status, review_stage=3,data={'project_name':status+str(i)},analysis={},competition_rule_package_id=package.id))
    db.session.commit();login(env[1],reviewer.id)
    first=env[1].get('/api/materials/competition/workbench-summary').json
    assert first['pending_count']==70
    assert len(first['items'])==50
    assert len(first['reviewed_items'])==50
    second=env[1].get('/api/materials/competition/workbench-summary',query_string={
        'before_id':first['next_before_id'],'reviewed_before_id':first['reviewed_next_before_id']}).json
    assert len(second['items'])==20
    assert len(second['reviewed_items'])==15
    assert second['next_before_id'] is None
    assert second['reviewed_next_before_id'] is None
    assert len({r['id'] for r in first['items']+second['items']})==70
