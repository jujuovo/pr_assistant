"""Volunteer material queue, exact gates, appeals and teacher scoring on a fresh DB."""
import io
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from conftest import login
from extensions import db
from models import User
from material_models import MaterialRecord, MaterialEvent
from ocr_models import OCRJob
from workflow_models import ScoreEntry
from services.competition_ocr.worker import run_one_ocr
from services.recognition.volunteer_material import extract
from test_ocr_workflow_integration import setup_formal, picture


class Provider:
    def __init__(self, hours='202', kind='普通志愿服务', day='2026年5月8日', score=.99):
        self.texts = [f'本次工时：{hours}小时', f'工时类别：{kind}', f'系统录入并审核通过日期：{day}']
        self.score = score

    def predict(self, path):
        return {'rec_texts': self.texts, 'rec_scores': [self.score] * len(self.texts)}


def upload(env, *, hours='202', reduced='0', day='2026-05-08', files=None):
    setup_formal(env)
    login(env[1], env[2]['student'])
    data = {'regular_hours': hours, 'reduced_hours': reduced, 'award_date': day}
    files = files or [(io.BytesIO(picture()), 'proof.png')]
    response = env[1].post('/api/materials/volunteer/records', data={
        'year': '2028', 'data': json.dumps(data), 'files': files})
    assert response.status_code == 201, response.json
    return response.json


def path(row):
    return f"/api/materials/volunteer/records/{row['id']}"


def refresh(env, row):
    return env[1].get(path(row)).json


def teacher(env):
    user = User(username='reviewer', password='test', name='教师', role='teacher', status='active',
                faculty_id=db.session.get(User, env[2]['student']).faculty_id)
    db.session.add(user); db.session.commit(); login(env[1], user.id)
    return user


def submit(env, row):
    return env[1].post(path(row)+'/submit', json={'version': row['version']})


def appeal(env, row, reason='原件清晰，OCR把工时数字识别错了，请老师核对。'):
    return env[1].post(path(row)+'/appeal', json={'version': row['version'], 'reason': reason})


def test_match_does_not_fill_fields_or_score_and_requires_teacher(env):
    row = upload(env)
    assert row['workflow_state'] == 'ocr_queued'
    assert 'submit' not in row['allowed_actions']
    assert submit(env, row).status_code == 409
    assert run_one_ocr(env[0], Provider())
    completed = refresh(env, row)
    assert completed['workflow_state'] == 'ready_to_submit'
    assert completed['data'] == row['data']
    assert completed['volunteer_ocr']['status'] == 'matched'
    assert all(c['matches'] for c in completed['volunteer_ocr']['comparisons'])
    assert not completed['priority_review'] and ScoreEntry.query.count() == 0
    submitted = submit(env, completed)
    assert submitted.status_code == 200, submitted.json
    teacher(env)
    result = env[1].post(path(row)+'/review', json={'version': submitted.json['version'],
        'decision': 'verified', 'comment': '', 'idempotency_key': 'volunteer-pass'})
    assert result.status_code == 200, result.json
    assert result.json['status'] == 'scored'
    assert str(ScoreEntry.query.filter_by(status='active').one().effective_score) == '0.0500'


@pytest.mark.parametrize('provider', [Provider(hours='201'), Provider(kind='支教'), Provider(day='2026年5月9日'), Provider(score=.5)])
def test_mismatch_or_unreliable_fields_return_before_teacher_review(env, provider):
    row = upload(env)
    assert run_one_ocr(env[0], provider)
    result = refresh(env, row)
    assert result['status'] == 'needs_correction'
    assert result['volunteer_ocr']['auto_returned']
    assert result['volunteer_ocr']['reasons']
    assert 'appeal' in result['allowed_actions'] and 'submit' not in result['allowed_actions']
    assert submit(env, result).status_code == 409
    teacher(env)
    assert env[1].get('/api/materials/volunteer/records').json['records'] == []
    assert ScoreEntry.query.count() == 0


def test_appeal_keeps_ocr_differences_enters_review_with_priority_and_no_score(env):
    row = upload(env)
    run_one_ocr(env[0], Provider(hours='200'))
    returned = refresh(env, row)
    assert appeal(env, returned, '  ').status_code == 400
    accepted = appeal(env, returned)
    assert accepted.status_code == 200, accepted.json
    result = accepted.json
    assert result['workflow_state'] == 'pending_review' and result['priority_review']
    assert result['appeal']['reason'].startswith('原件清晰')
    assert result['ocr_raw_terms'] == returned['ocr_raw_terms']
    assert result['volunteer_ocr']['comparisons'] == returned['volunteer_ocr']['comparisons']
    assert appeal(env, result).status_code == 409
    assert ScoreEntry.query.count() == 0
    teacher(env)
    pending = env[1].get('/api/materials/volunteer/records').json['records']
    assert len(pending) == 1 and pending[0]['priority_review']
    result = env[1].post(path(row)+'/review', json={'version': result['version'],
        'decision': 'verified', 'comment': '', 'idempotency_key': 'appeal-pass'})
    assert result.status_code == 200, result.json
    assert ScoreEntry.query.count() == 1
    assert MaterialEvent.query.filter_by(record_id=row['id'], action='appealed').count() == 1


@pytest.mark.parametrize('filename,payload', [('proof.pdf', b'%PDF test'), ('bad.png', b'not image')])
def test_unrecognizable_original_is_returned_and_can_appeal(env, filename, payload):
    row = upload(env, files=[(io.BytesIO(payload), filename)])
    assert row['status'] == 'needs_correction' and 'appeal' in row['allowed_actions']
    assert not row['volunteer_ocr']['jobs']
    result = appeal(env, row, '原件格式未适配，请教师人工核对。')
    assert result.status_code == 200, result.json
    assert result.json['priority_review']


def test_worker_failure_has_appeal_path(env):
    row = upload(env)
    class Broken:
        def predict(self, path): raise RuntimeError('model unavailable')
    assert run_one_ocr(env[0], Broken())
    result = refresh(env, row)
    assert result['volunteer_ocr']['status'] == 'returned'
    assert result['ocr_raw_terms']['reports'][0]['error']
    assert appeal(env, result).status_code == 200


def test_changed_facts_invalidate_running_result_and_retry_uses_new_version(env):
    row = upload(env)
    changed = env[1].patch(path(row), json={'version': row['version'], 'data': row['data'] | {'regular_hours': '200'}})
    assert changed.status_code == 200
    assert run_one_ocr(env[0], Provider())
    current = refresh(env, row)
    assert current['status'] == 'draft' and current['volunteer_ocr'] is None
    assert 'recognize' in current['allowed_actions']
    assert submit(env, current).status_code == 409
    retried = env[1].post(path(row)+'/ocr', json={'version': current['version']})
    assert retried.status_code == 202, retried.json
    assert run_one_ocr(env[0], Provider(hours='200'))
    assert refresh(env, row)['volunteer_ocr']['status'] == 'matched'


def test_numeric_format_is_normalized_and_dates_are_not_checkin_dates():
    data = Provider(hours='202.0000').predict(None)
    assert extract(data)['fields']['hours'] == '202'
    page = {'rec_texts': ['本次工时：202小时', '普通志愿服务', '签到时间：2026年5月8日', '签退时间：2026年5月8日'], 'rec_scores': [.99]*4}
    assert extract(page)['fields']['award_date'] is None
    ambiguous = Provider().predict(None)
    ambiguous['rec_texts'].append('认定日期：2026年5月9日'); ambiguous['rec_scores'].append(.99)
    assert extract(ambiguous)['fields']['award_date'] is None


def test_appeal_and_jobs_cannot_be_read_or_written_by_other_faculty(env):
    row = upload(env)
    run_one_ocr(env[0], Provider(hours='200'))
    returned = refresh(env, row)
    login(env[1], env[2]['other'])
    assert appeal(env, returned).status_code == 403
    assert env[1].get('/api/ocr/jobs/'+row['volunteer_ocr']['jobs'][0]).status_code == 403
    assert env[1].get(path(row)).status_code == 403


def test_appeal_never_bypasses_original_integrity(env):
    row = upload(env)
    run_one_ocr(env[0], Provider(hours='200'))
    returned = refresh(env, row)
    from services.materials.service import stored_path
    original = db.session.get(MaterialRecord, row['id']).attachments[0]
    stored_path(original.stored_name).write_bytes(b'changed')
    result = appeal(env, returned)
    assert result.status_code == 409 and result.json['code'] == 'original_integrity_failed'
    current = refresh(env, row)
    assert current['status'] == 'needs_correction' and current['appeal'] is None
    assert MaterialEvent.query.filter_by(action='appealed').count() == 0


def test_transaction_failure_cleans_ocr_and_original_files(env):
    setup_formal(env)
    with patch.object(db.session, 'commit', side_effect=RuntimeError('commit failure')):
        with pytest.raises(RuntimeError):
            login(env[1], env[2]['student'])
            env[1].post('/api/materials/volunteer/records', data={
                'year': '2028', 'data': json.dumps({'regular_hours':'202','reduced_hours':'0','award_date':'2026-05-08'}),
                'files': (io.BytesIO(picture()), 'proof.png')})
    assert MaterialRecord.query.count() == OCRJob.query.count() == 0
    assert not list(Path(env[0].config['OCR_STORAGE_FOLDER']).glob('*'))


def test_reduced_hours_match_in_original_hours_without_premature_halving(env):
    row=upload(env,hours='0',reduced='202')
    run_one_ocr(env[0],Provider(kind='大型赛会或支教'))
    result=refresh(env,row)
    assert result['volunteer_ocr']['status']=='matched'
    assert result['analysis']['submitted_hours']['effective_hours']=='101'


def test_multiple_proofs_are_all_processed_and_hours_summed_once(env):
    from PIL import Image
    different=io.BytesIO()
    Image.new('RGB',(800,600),'#eef7ff').save(different,format='PNG');different.seek(0)
    row=upload(env,files=[(io.BytesIO(picture()),'one.png'),(different,'two.png')])
    assert len(row['volunteer_ocr']['jobs'])==2
    run_one_ocr(env[0],Provider(hours='20'))
    assert refresh(env,row)['workflow_state']=='ocr_queued'
    run_one_ocr(env[0],Provider(hours='182'))
    result=refresh(env,row)
    assert result['volunteer_ocr']['status']=='matched'
    assert len(result['ocr_raw_terms']['reports'])==2
    assert result['volunteer_ocr']['comparisons'][0]['recognized']=='202'


def test_duplicate_images_are_returned_rather_than_double_counted(env):
    row=upload(env,files=[(io.BytesIO(picture()),'one.png'),(io.BytesIO(picture()),'duplicate.png')])
    run_one_ocr(env[0],Provider())
    result=refresh(env,row)
    assert result['volunteer_ocr']['status']=='returned'
    assert any('重复' in reason for reason in result['volunteer_ocr']['reasons'])


def test_stale_version_and_completed_tasks_cannot_submit_duplicate_appeals(env):
    row=upload(env);run_one_ocr(env[0],Provider(hours='200'))
    returned=refresh(env,row)
    stale=returned|{'version':returned['version']-1}
    response=appeal(env,stale)
    assert response.status_code==409 and refresh(env,row)['status']=='needs_correction'
    accepted=appeal(env,returned)
    assert accepted.status_code==200
    assert not run_one_ocr(env[0],Provider())
    assert refresh(env,row)['priority_review']


def test_rule_notice_cannot_leave_a_stale_job_permanently_queued(env):
    row=upload(env)
    record=db.session.get(MaterialRecord,row['id']);record.version+=1;db.session.commit()
    current=refresh(env,row)
    assert current['volunteer_ocr']['status']=='stale'
    assert current['workflow_state']=='draft' and 'recognize' in current['allowed_actions']
    run_one_ocr(env[0],Provider())
    assert refresh(env,row)['volunteer_ocr']['status']=='stale'


def test_classification_must_be_explicit_not_inferred_from_a_rule_footer():
    page=Provider().predict(None)
    page['rec_texts'][1]='备注：非支教项目，不属于大型赛会'
    assert extract(page)['fields']['service_type'] is None


def credit_page(noise=False):
    texts=['信用时数详情','+5.05','签到时间','签退时间','2025年12月21日','12:33:03','2025年12月21日','17:36:34','参与活动','信息学院志愿服务']
    boxes=[[350,100,650,140],[400,300,600,370],[100,400,300,430],[650,400,850,430],
           [70,480,360,510],[110,530,280,560],[620,480,900,510],[660,530,830,560],
           [20,700,160,730],[200,700,750,730]]
    scores=[.99]*len(texts)
    if noise:
        texts.insert(1,'2');boxes.insert(1,[450,200,500,220]);scores.insert(1,.14)
    return {'rec_texts':texts,'rec_scores':scores,'rec_boxes':boxes}


def test_credit_platform_uses_coordinates_and_applies_ordinary_service_policy():
    result=extract(credit_page(),1000)
    assert result['fields']['hours']=='5.05'
    assert result['fields']['check_in']=='2025-12-21T12:33:03'
    assert result['fields']['check_out']=='2025-12-21T17:36:34'
    assert result['fields']['activity_name']=='信息学院志愿服务'
    assert result['fields']['service_type']=='regular' and result['fields']['award_date']=='2025-12-21'
    assert result['missing_fields']==[]
    assert result['platform_policy']['date_basis']=='credit_check_out'


def test_low_quality_icon_glyph_does_not_hide_a_clear_displayed_number():
    result=extract(credit_page(noise=True),1000)
    assert result['platform_baseline']['fields']['displayed_hours']['value'] is None
    assert result['noise_filtered'] and result['fields']['hours']=='5.05'
    page=credit_page(noise=True);page['rec_scores'][1]=.99
    assert extract(page,1000)['fields']['hours'] is None  # Two readable candidates stay ambiguous.


def test_credit_screenshot_matches_all_three_declared_fields(env):
    row=upload(env,hours='5.05',day='2025-12-21')
    class PlatformProvider:
        def predict(self,path):return credit_page()
    run_one_ocr(env[0],PlatformProvider())
    result=refresh(env,row)
    assert result['workflow_state']=='ready_to_submit'
    comparisons={item['field']:item for item in result['volunteer_ocr']['comparisons']}
    assert comparisons['hours']['recognized']=='5.05' and comparisons['hours']['matches']
    assert comparisons['service_type']['recognized']=='普通志愿服务'
    assert comparisons['award_date']['recognized']=='2025-12-21'
    assert all(item['matches'] for item in comparisons.values())
    assert result['ocr_raw_terms']['reports'][0]['report']['fields']['check_in']
    assert 'submit' in result['allowed_actions'] and 'appeal' not in result['allowed_actions']


def test_empty_report_is_unknown_instead_of_zero(env):
    from services.volunteer_ocr import comparisons
    row=upload(env);record=db.session.get(MaterialRecord,row['id'])
    values,_=comparisons(record,[])
    assert all(item['recognized'] is None and item['reason']=='missing' for item in values)


def honor_page():
    texts=['荣誉时数详情','+12','基础信息','录入时间','2026-09-1416:12:07']
    boxes=[[300,100,650,150],[400,300,600,370],[40,450,240,490],[40,600,240,640],[400,600,780,640]]
    return {'rec_texts':texts,'rec_scores':[.99]*len(texts),'rec_boxes':boxes}


def test_honor_screenshot_matches_all_three_fields_using_recorded_date(env):
    row=upload(env,hours='12',day='2026-09-14')
    class HonorProvider:
        def predict(self,path):return honor_page()
    run_one_ocr(env[0],HonorProvider())
    result=refresh(env,row)
    assert result['workflow_state']=='ready_to_submit'
    assert len(result['volunteer_ocr']['comparisons'])==3
    assert all(item['matches'] for item in result['volunteer_ocr']['comparisons'])
    report=result['ocr_raw_terms']['reports'][0]['report']
    assert report['platform_policy']['date_basis']=='honor_recorded_at'
    assert report['fields']['award_date']=='2026-09-14'
    assert report['fields']['service_type']=='regular'
    assert ScoreEntry.query.count()==0


@pytest.mark.parametrize('hours,reduced,day', [('5.06','0','2025-12-21'),('0','5.05','2025-12-21'),('5.05','0','2025-12-22')])
def test_screenshot_does_not_override_wrong_student_hours_type_or_date(env,hours,reduced,day):
    row=upload(env,hours=hours,reduced=reduced,day=day)
    class PlatformProvider:
        def predict(self,path):return credit_page()
    run_one_ocr(env[0],PlatformProvider())
    result=refresh(env,row)
    assert result['status']=='needs_correction' and 'appeal' in result['allowed_actions']
    assert any(not item['matches'] for item in result['volunteer_ocr']['comparisons'])
    assert result['data']==row['data']


def test_credit_date_requires_ordered_checkin_and_checkout_and_uses_completion_day():
    page=credit_page()
    page['rec_texts'][6]='2025年12月22日'
    result=extract(page,1000)
    assert result['fields']['award_date']=='2025-12-22'
    page['rec_texts'][6]='2025年12月20日'
    result=extract(page,1000)
    assert result['fields']['award_date'] is None and 'award_date' in result['missing_fields']


def test_screenshot_title_without_layout_or_times_cannot_pass_the_policy():
    page=credit_page()
    for i in (4,5,6,7):page['rec_texts'][i]='模糊不可读'
    result=extract(page,1000)
    assert result['fields']['hours']=='5.05'
    assert result['fields']['award_date'] is None
    assert result['fields']['service_type'] is None
    assert not result['platform_policy']['screen_matched']


def test_low_quality_datetime_is_not_accepted_as_a_reliable_match():
    page=credit_page();page['rec_scores'][4]=.5
    result=extract(page,1000)
    assert result['fields']['award_date']=='2025-12-21'
    assert 'award_date' in result['missing_fields']
