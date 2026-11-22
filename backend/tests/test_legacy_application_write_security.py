"""Compatibility writes must never rely on a certificate flag for authorization."""
from pathlib import Path
from unittest.mock import patch
import pytest
from conftest import login
from extensions import db
from models import Application, Student, User, Rule
from certificate_models import CertificateAssessment
from workflow_models import ScoreEntry, RuleVersion


def draft(env,status='draft',owner='S1',**extra):
    s=Student.query.filter_by(student_id=owner).one()
    row=Application(student_id=s.student_id,student_name=s.student_name,faculty_id=s.faculty_id,
        department_id=s.department_id,major_id=s.major_id,application_type='academic',project_name='历史申请',
        status=status,self_score=1,**extra)
    db.session.add(row);db.session.commit();return row


def url(row):return f'/api/applications/{row.id}'


@pytest.mark.parametrize('method,suffix',[('post',''),('put','/1'),('delete','/1'),('post','/1/review')])
def test_unauthenticated_legacy_writes_are_rejected_before_changes(env,method,suffix):
    row=draft(env)
    response=getattr(env[1],method)('/api/applications'+suffix,json={'projectName':'unauthorized'})
    assert response.status_code==401
    assert db.session.get(Application,row.id).project_name=='历史申请'


def test_student_identity_is_bound_to_session_not_frontend(env):
    login(env[1],env[2]['student'])
    forged=env[1].post('/api/applications',json={'studentId':'someone-else','applicationType':'academic','projectName':'冒用申请','status':'draft'})
    assert forged.status_code==403 and Application.query.count()==0
    accepted=env[1].post('/api/applications',json={'applicationType':'academic','projectName':'本人申请','status':'draft'})
    assert accepted.status_code==201,accepted.json
    row=Application.query.one();student=Student.query.one()
    assert row.student_id==student.student_id and row.faculty_id==student.faculty_id


@pytest.mark.parametrize('action',['create','edit','review','delete'])
def test_foreign_faculty_teacher_cannot_write_another_students_application(env,action):
    row=draft(env,status='pending' if action=='review' else 'draft')
    login(env[1],env[2]['other'])
    if action=='create':response=env[1].post('/api/applications',json={'studentId':'S1','applicationType':'academic','projectName':'越权创建','status':'draft'})
    elif action=='edit':response=env[1].put(url(row),json={'projectName':'越权修改'})
    elif action=='delete':response=env[1].delete(url(row))
    else:response=env[1].post(url(row)+'/review',json={'status':'approved'})
    assert response.status_code==403
    assert Application.query.count()==1 and db.session.get(Application,row.id).project_name=='历史申请'


@pytest.mark.parametrize('status',['approved','rejected'])
def test_processed_applications_are_readonly_for_student_and_teacher(env,status):
    row=draft(env,status=status)
    login(env[1],env[2]['student'])
    assert env[1].put(url(row),json={'projectName':'不能覆盖历史'}).status_code==409
    assert env[1].delete(url(row)).status_code==409
    login(env[1],env[2]['admin'])
    assert env[1].post(url(row)+'/review',json={'status':'approved'}).status_code==409
    assert db.session.get(Application,row.id).status==status


@pytest.mark.parametrize('field,value',[('applicationType','invention_patent'),('application_type','research_paper'),('sub_type','competition')])
def test_edit_cannot_reclassify_a_legacy_draft_into_a_migrated_category(env,field,value):
    row=draft(env);login(env[1],env[2]['student'])
    response=env[1].put(url(row),json={field:value})
    assert response.status_code==409 and response.json['route'].startswith('/api/materials/')
    assert db.session.get(Application,row.id).application_type=='academic'


def test_migrated_rule_cannot_be_disguised_as_another_category(env):
    s=Student.query.one()
    rule=Rule(name='专利规则',type='academic',sub_type='research',research_type='patent',faculty_id=s.faculty_id,status='active',score=2)
    db.session.add(rule);db.session.commit();login(env[1],env[2]['student'])
    payload={'ruleId':rule.id,'applicationType':'academic','projectName':'伪装类别','status':'draft'}
    assert env[1].post('/api/applications',json=payload).status_code==409
    row=draft(env)
    assert env[1].put(url(row),json={'ruleId':rule.id}).status_code==409
    assert db.session.get(Application,row.id).rule_id is None


def test_update_cannot_change_identity_score_or_other_attachment(env):
    row=draft(env);login(env[1],env[2]['student'])
    # 身份篡改按越权处理（403），审核字段按状态冲突处理（409），附件白名单仍是格式错误（400）
    for payload, expected in (({'studentId':'S2'},403),({'finalScore':100},409),
                              ({'files':[{'path':'/uploads/files/other.png'}]},400)):
        assert env[1].put(url(row),json=payload).status_code==expected
    assert env[1].put(url(row),json={'projectName':'正常修改'}).status_code==200
    assert db.session.get(Application,row.id).project_name=='正常修改'


def test_assessment_deletion_is_blocked_even_when_sqlite_fk_is_disabled(env):
    row=draft(env)
    db.session.add(CertificateAssessment(application_id=row.id,project_key='manual',status='manual',claims={},sources=[],artifact_key='test',version=1,attempts=0));db.session.commit()
    login(env[1],env[2]['student'])
    assert env[1].delete(url(row)).status_code==409
    assert Application.query.count()==CertificateAssessment.query.count()==1


def test_draft_delete_preserves_files_if_commit_fails(env):
    root=Path(env[0].config['FILE_FOLDER']);root.mkdir(parents=True,exist_ok=True)
    file=root/'proof.png';file.write_bytes(b'original')
    row=draft(env,files=[{'name':'proof.png','path':'/uploads/files/proof.png'}])
    login(env[1],env[2]['student'])
    with patch.object(db.session,'commit',side_effect=RuntimeError('forced rollback')):
        with pytest.raises(RuntimeError):env[1].delete(url(row))
    db.session.rollback()
    assert db.session.get(Application,row.id) and file.read_bytes()==b'original'


def test_only_unsubmitted_unlinked_own_draft_is_physically_deleted(env):
    row=draft(env);login(env[1],env[2]['student'])
    assert env[1].delete(url(row)).status_code==200
    assert Application.query.count()==0
    row=draft(env,status='pending')
    assert env[1].delete(url(row)).status_code==409


@pytest.mark.parametrize('action', ['edit', 'delete'])
def test_another_student_in_same_faculty_cannot_modify_application(env, action):
    row = draft(env)
    owner = Student.query.one()
    student = Student(student_id='S2', student_name='李四', faculty_id=owner.faculty_id,
                      department_id=owner.department_id, major_id=owner.major_id)
    user = User(username='second', name='李四', password='test', role='student',
                status='active', student_id='S2', faculty_id=owner.faculty_id)
    db.session.add_all([student, user]); db.session.commit()
    login(env[1], user.id)
    response = (env[1].put(url(row), json={'projectName': '越权'}) if action == 'edit'
                else env[1].delete(url(row)))
    assert response.status_code == 403
    assert db.session.get(Application, row.id).project_name == '历史申请'


def test_clearing_rule_id_cannot_reopen_migrated_history_for_edit(env):
    owner = Student.query.one()
    rule = Rule(name='旧竞赛规则', type='academic', sub_type='competition',
                faculty_id=owner.faculty_id, score=1, status='active')
    db.session.add(rule); db.session.commit()
    row = draft(env, rule_id=rule.id)
    login(env[1], env[2]['student'])
    response = env[1].put(url(row), json={'ruleId': None, 'applicationType': 'academic'})
    assert response.status_code == 409
    assert db.session.get(Application, row.id).rule_id == rule.id


def test_foreign_faculty_rule_is_rejected_before_creation(env):
    from models import Faculty
    rule = Rule(name='外院规则', type='academic', sub_type='honor', score=1,
                faculty_id=Faculty.query.filter_by(name='其他学院').one().id, status='active')
    db.session.add(rule); db.session.commit()
    login(env[1], env[2]['student'])
    response = env[1].post('/api/applications', json={
        'ruleId': rule.id, 'applicationType': 'academic', 'projectName': '跨院', 'status': 'draft'})
    assert response.status_code == 403 and Application.query.count() == 0


@pytest.mark.parametrize('score_status', ['active', 'invalidated'])
def test_even_historical_score_evidence_blocks_draft_deletion(env, active_honor_rule, score_status):
    row = draft(env)
    db.session.add(ScoreEntry(student_id=row.student_id, faculty_id=row.faculty_id,
        year=2026, rule_version_id=RuleVersion.query.filter_by(rule_id=active_honor_rule.id).one().id,
        score_group='academic', category='honor', source_type='legacy_application',
        source_id=str(row.id), source_revision=1, raw_score=1, adjusted_score=1,
        effective_score=1, status=score_status, idempotency_key='history-proof'))
    db.session.commit(); login(env[1], env[2]['student'])
    assert env[1].delete(url(row)).status_code == 409
    assert Application.query.count() == ScoreEntry.query.count() == 1


@pytest.mark.parametrize('payload', [None, [], {}, {'status': 'pending'}, {'status': 'made-up'}])
def test_invalid_review_decision_cannot_change_pending_application(env, payload):
    row = draft(env, status='pending'); login(env[1], env[2]['admin'])
    response = env[1].post(url(row)+'/review', json=payload)
    assert response.status_code == 400
    assert db.session.get(Application, row.id).status == 'pending'


def test_review_once_preserves_first_score_and_blocks_later_overwrite(env, active_honor_rule):
    row = draft(env, status='pending', rule_id=active_honor_rule.id, cycle_code=2026)
    # A real fixed cycle is required by the score adapter.
    from workflow_models import RecommendationCyclePolicy
    row.cycle_policy_version_id = RecommendationCyclePolicy.query.filter_by(status='active').one().id
    db.session.commit(); login(env[1], env[2]['admin'])
    first = env[1].post(url(row)+'/review', json={'status': 'approved'})
    assert first.status_code == 200, first.json
    original_score = db.session.get(Application, row.id).final_score
    score_ids = [entry.id for entry in ScoreEntry.query.all()]
    assert len(score_ids) == 1
    second = env[1].post(url(row)+'/review', json={'status': 'rejected', 'reviewComment': '覆盖'})
    assert second.status_code == 409
    assert db.session.get(Application, row.id).status == 'approved'
    assert db.session.get(Application, row.id).final_score == original_score
    assert [entry.id for entry in ScoreEntry.query.all()] == score_ids


@pytest.mark.parametrize('loaded', [False, True])
def test_orm_parent_deletion_cannot_cascade_certificate_evidence(env, loaded):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    row = draft(env)
    evidence = CertificateAssessment(application_id=row.id, project_key='manual', status='manual',
        claims={}, sources=[], artifact_key='evidence', version=1, attempts=0)
    db.session.add(evidence); db.session.commit()
    row_id, evidence_id = row.id, evidence.id
    db.session.remove()
    db.session.execute(text('PRAGMA foreign_keys=ON'))
    row = db.session.get(Application, row_id)
    if loaded:
        assert row.certificate_assessment.id == evidence_id
    db.session.delete(row)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert db.session.get(Application, row_id)
    assert db.session.get(CertificateAssessment, evidence_id)
    db.session.remove()
    # The remaining tests intentionally use incomplete fixtures with FK checks disabled.
    db.session.execute(text('PRAGMA foreign_keys=OFF'))
