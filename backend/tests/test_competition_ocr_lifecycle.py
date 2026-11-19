import json
from pathlib import Path

import pytest

from extensions import db
from models import User
from use_cases.competition_ocr import (
    cancel_competition_ocr, complete_competition_ocr, fail_competition_ocr,
    start_competition_ocr,
)
from use_cases.competition_rules import load_current_competition_package
from use_cases.materials import MaterialUseCaseError, create_material, edit_material


def draft(env):
    admin = db.session.get(User, env[2]['admin'])
    snapshot = json.loads(
        (Path(__file__).parents[1] / 'rules' / 'competition_2028.json').read_text(encoding='utf-8')
    )
    load_current_competition_package(admin, snapshot)
    student = db.session.get(User, env[2]['student'])
    row = create_material(student, 'competition', {'year': 2028, 'data': {
        'competition_id': 'c09-computer-design', 'project_name': '手填作品',
        'award_date': '2027-05-01', 'level': 'national',
        'award': 'first_or_above', 'event_year': 2027,
        'participation_mode': 'individual',
    }})
    db.session.flush()
    return student, row


def manual_facts(name):
    return {
        'competition_id': 'c09-computer-design', 'project_name': name,
        'award_date': '2027-05-01', 'level': 'national',
        'award': 'first_or_above', 'event_year': 2027,
        'participation_mode': 'individual',
    }


def test_cancel_then_manual_edit_ignores_late_worker_result(env):
    student, row = draft(env)
    job, created = start_competition_ocr(student, row, row.version)
    assert created is True
    cancel_competition_ocr(student, row, row.version, job.job_id)
    edit_material(student, row, row.version, manual_facts('学生确认名称'))
    confirmed = dict(row.confirmed_terms)
    completed, authoritative = complete_competition_ocr(
        job.job_id, {'project_name': '迟到 OCR 名称'}
    )
    assert authoritative is False
    assert completed.status == 'ignored'
    assert completed.ignored_late_result['project_name'] == '迟到 OCR 名称'
    assert row.confirmed_terms == confirmed
    assert row.ocr_raw_terms is None


def test_successful_ocr_saves_raw_result_without_overwriting_confirmation(env):
    student, row = draft(env)
    confirmed = dict(row.confirmed_terms)
    job, _ = start_competition_ocr(student, row, row.version)
    completed, authoritative = complete_competition_ocr(job.job_id, {'raw': 'OCR 原文'})
    assert authoritative is True
    assert completed.status == 'completed'
    assert row.ocr_raw_terms == {'raw': 'OCR 原文'}
    assert row.confirmed_terms == confirmed


def test_failed_ocr_keeps_manual_path_available(env):
    student, row = draft(env)
    job, _ = start_competition_ocr(student, row, row.version)
    fail_competition_ocr(job.job_id, 'provider unavailable')
    edit_material(student, row, row.version, manual_facts('失败后手填'))
    assert job.status == 'failed'
    assert row.confirmed_terms['project_name'] == '失败后手填'


def test_cancel_uses_material_version_cas(env):
    student, row = draft(env)
    job, _ = start_competition_ocr(student, row, row.version)
    with pytest.raises(MaterialUseCaseError) as error:
        cancel_competition_ocr(student, row, row.version + 1, job.job_id)
    assert error.value.code == 'version_conflict'
