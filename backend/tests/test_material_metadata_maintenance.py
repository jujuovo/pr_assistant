from datetime import datetime, timezone, timedelta
import pytest
from conftest import login
from extensions import db
from material_models import MaterialRecord, MaterialEvent
from services.time_format import utc_timestamp


@pytest.mark.parametrize('value,expected', [
    (None, None),
    (datetime(2026,11,21,10,30,12), '2026-11-21T10:30:12Z'),
    (datetime(2026,11,21,18,30,12,tzinfo=timezone(timedelta(hours=8))), '2026-11-21T10:30:12Z'),
    (datetime(2026,11,21,10,30,12,tzinfo=timezone.utc), '2026-11-21T10:30:12Z'),
])
def test_material_timestamp_uses_explicit_utc(value, expected):
    assert utc_timestamp(value) == expected


def test_summary_record_and_history_timestamps_represent_the_same_instant(env):
    from test_ocr_workflow_integration import setup_formal, facts
    setup_formal(env)
    login(env[1],env[2]['student'])
    created=env[1].post('/api/materials/competition/records',json={'year':2028,'data':facts()})
    assert created.status_code==201,created.json
    row=db.session.get(MaterialRecord,created.json['id'])
    instant=datetime(2026,11,21,10,30,12)
    row.updated_at=instant
    row.status='needs_correction'
    db.session.add(MaterialEvent(record_id=row.id,actor_id=env[2]['admin'],action='competition_returned',
                                details={'comment':'核对日期'},created_at=instant))
    db.session.commit()
    summary=env[1].get('/api/materials/competition/workbench-summary').json
    item=next(item for item in summary['items'] if item['id']==row.id)
    record=env[1].get(f'/api/materials/competition/records/{row.id}').json
    history=env[1].get(f'/api/materials/competition/records/{row.id}/events').json['events']
    assert item['updated_at']==item['review']['at']==record['updated_at']==history[-1]['created_at']=='2026-11-21T10:30:12Z'
    assert record['data']['award_date']==facts()['award_date']


def test_category_scoring_capabilities_do_not_claim_new_ocr_support(env):
    login(env[1],env[2]['student'])
    response=env[1].get('/api/materials/types')
    assert response.status_code==200
    types={item['key']:item for item in response.json['types']}
    enabled={'competition','volunteer','research_paper','invention_patent','innovation_training','student_work'}
    assert {key for key,item in types.items() if item['auto_bonus_enabled']}==enabled
    for key in ('research_paper','invention_patent','innovation_training'):
        assert types[key]['recognition_status']=='not_implemented'
        assert not types[key]['manual_only']
    for key in ('arts_sports','social_practice','competition_evidence'):
        assert types[key]['manual_only'] and not types[key]['auto_bonus_enabled']
