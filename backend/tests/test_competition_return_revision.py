import json
from datetime import date
from pathlib import Path

import pytest

from conftest import login
from extensions import db
from material_models import MaterialEvent, MaterialRecord
from models import User
from use_cases.competition_rules import load_current_competition_package
from use_cases.materials import (
    MaterialUseCaseError, abandon_returned_competition,
    competition_workbench_summary, create_correction_version, create_material,
)


def returned_material(env):
    admin = db.session.get(User, env[2]['admin'])
    snapshot = json.loads(
        (Path(__file__).parents[1] / 'rules' / 'competition_2028.json').read_text(encoding='utf-8')
    )
    package, _ = load_current_competition_package(admin, snapshot)
    student = db.session.get(User, env[2]['student'])
    facts = {
        'competition_id': 'c09-computer-design', 'project_name': '原作品',
        'award_date': '2027-05-01', 'level': 'national',
        'award': 'first_or_above', 'event_year': 2027,
        'participation_mode': 'individual',
    }
    row = create_material(student, 'competition', {'year': 2028, 'data': facts})
    row.status = 'needs_correction'
    row.competition_duplicate_digest = 'a' * 64
    db.session.add(MaterialEvent(
        record_id=row.id, actor_id=admin.id, action='competition_returned',
        details={'comment': '请核对作品名称'},
    ))
    db.session.flush()
    return student, row, facts, package


def test_returned_material_creates_new_version_and_preserves_original_history(env):
    student, original, facts, package = returned_material(env)
    corrected = create_correction_version(
        student, original, original.version, {**facts, 'project_name': '修正作品'}
    )
    db.session.flush()
    assert corrected.id != original.id
    assert corrected.supersedes_record_id == original.id
    assert corrected.correction_sequence == 1
    assert corrected.status == 'draft'
    assert corrected.competition_rule_package_id == package.id
    assert original.status == 'needs_correction'
    assert original.competition_duplicate_digest is None
    assert any(event.details.get('comment') == '请核对作品名称' for event in original.events)


def test_returned_material_can_be_abandoned_without_deleting_history(env):
    student, original, _facts, _package = returned_material(env)
    abandon_returned_competition(student, original, original.version)
    db.session.flush()
    assert original.status == 'abandoned'
    assert db.session.get(MaterialRecord, original.id) is original
    assert any(event.action == 'competition_returned' for event in original.events)
    assert any(event.action == 'abandon' for event in original.events)


def test_draft_can_be_abandoned_without_deleting_history(env):
    student, _returned, facts, _package = returned_material(env)
    draft = create_material(student, 'competition', {'year': 2028, 'data': facts})
    abandon_returned_competition(student, draft, draft.version)
    db.session.flush()
    assert draft.status == 'abandoned'
    assert db.session.get(MaterialRecord, draft.id) is draft
    assert any(event.action == 'abandon' for event in draft.events)


def test_return_opinion_text_is_never_parsed_to_decide_resubmission(env):
    student, original, facts, _package = returned_material(env)
    original.events[-1].details = {'comment': '不得重提（仅为教师自由文本）'}
    corrected = create_correction_version(student, original, original.version, facts)
    assert corrected.status == 'draft'


def test_return_revision_checks_owner_and_version(env):
    student, original, facts, _package = returned_material(env)
    outsider = db.session.get(User, env[2]['other'])
    with pytest.raises(MaterialUseCaseError) as forbidden:
        create_correction_version(outsider, original, original.version, facts)
    assert forbidden.value.code == 'forbidden'
    with pytest.raises(MaterialUseCaseError) as conflict:
        create_correction_version(student, original, original.version + 1, facts)
    assert conflict.value.code == 'version_conflict'


def test_existing_correction_supersedes_old_workbench_action_and_blocks_duplicate(env):
    student, original, facts, _package = returned_material(env)
    from use_cases.cycles import activate_cycle_policy, create_cycle_policy
    admin = db.session.get(User, env[2]['admin'])
    policy, _ = create_cycle_policy(
        admin, 2028, date(2025, 9, 1), date(2028, 8, 31), '2028 推免周期'
    )
    activate_cycle_policy(admin, policy)
    corrected = create_correction_version(student, original, original.version, facts)
    db.session.flush()

    summary = competition_workbench_summary(student)
    assert summary['needs_correction_count'] == 0
    assert summary['status_counts'] == {'draft': 1}
    assert [item['id'] for item in summary['items']] == [corrected.id]

    with pytest.raises(MaterialUseCaseError) as duplicate:
        create_correction_version(student, original, original.version, facts)
    assert duplicate.value.code == 'correction_already_exists'

    db.session.commit()
    login(env[1], env[2]['student'])
    records = env[1].get('/api/materials/competition/records?year=2028').json['records']
    old_projection = next(item for item in records if item['id'] == original.id)
    assert old_projection['superseded_by_record_id'] == corrected.id
    assert old_projection['allowed_actions'] == []


def test_abandoned_correction_does_not_lock_original_material(env):
    """放弃补正稿后，被退回的原材料必须重新可补正，不能两条记录同时卡死。"""
    student, original, facts, _package = returned_material(env)
    corrected = create_correction_version(student, original, original.version, facts)
    db.session.flush()
    abandon_returned_competition(student, corrected, corrected.version)
    db.session.flush()

    again = create_correction_version(student, original, original.version, facts)
    db.session.flush()
    assert again.status == 'draft'
    assert again.id != corrected.id
    assert again.supersedes_record_id == original.id


def test_correction_version_inherits_original_attachments(env):
    """补正稿必须继承原件：改一个日期不该被要求重新上传扫描件。"""
    import os

    from services.materials.service import stored_path
    from use_cases.materials import add_attachments

    student, original, facts, _package = returned_material(env)
    add_attachments(
        student, original, original.version,
        [("proof.png", b"proof-bytes")], stored_path("placeholder").parent,
    )
    db.session.flush()
    # 上传附件会把材料状态改回 draft，这里恢复成教师退回后的状态
    original.status = "needs_correction"
    db.session.flush()
    assert original.attachments
    version = original.version

    corrected = create_correction_version(student, original, version, facts)
    db.session.flush()
    assert len(corrected.attachments) == len(original.attachments)
    source = original.attachments[0]
    inherited = corrected.attachments[0]
    assert inherited.filename == source.filename
    assert inherited.sha256 == source.sha256
    # 必须复制成新文件，不能共用存储名，否则一方删除会丢另一方原件
    assert inherited.stored_name != source.stored_name
    assert stored_path(inherited.stored_name).is_file()
    for path in (stored_path(source.stored_name), stored_path(inherited.stored_name)):
        os.remove(path)


def test_student_projection_exposes_last_review_comment(env):
    """学生必须能读到自己为什么被退回，否则无法按要求补正。"""
    student, original, _facts, _package = returned_material(env)
    db.session.commit()
    login(env[1], env[2]['student'])
    records = env[1].get('/api/materials/competition/records?year=2028').json['records']
    projection = next(item for item in records if item['id'] == original.id)
    assert 'create_correction' in projection['allowed_actions']
    assert projection['superseded_by_record_id'] is None
    assert projection['last_review']['decision'] == 'return'
    assert projection['last_review']['comment'] == '请核对作品名称'
    assert projection['last_review']['actor']['role'] == 'admin'
