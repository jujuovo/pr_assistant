"""Fresh SQLite API acceptance, optionally with local real OCR. No browser automation."""
import argparse
import io
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def run(database, real_ocr=False):
    database=database.resolve()
    if database.exists():
        raise ValueError("验收须使用未存在的独立数据库；不会删除或覆盖现有数据")
    from tools.prepare_local import main
    main(database)
    from app import app
    from extensions import db
    from models import User, Application
    from material_models import MaterialRecord
    from workflow_models import ScoreEntry
    from services.competition_ocr.worker import run_one_ocr
    from services.recognition.provider import PaddleProvider
    storage=database.parent/(database.stem+'-files')
    app.config.update(TESTING=True, OCR_STORAGE_FOLDER=str(storage/'ocr'), MATERIAL_STORAGE_FOLDER=str(storage/'evidence'))
    with app.app_context():
        client=app.test_client()
        student=User.query.filter_by(username='student001').one()
        teacher=User.query.filter_by(username='teacher001').one()
        admin=User.query.filter_by(username='admin001').one()
        with client.session_transaction() as session:session['user_id']=student.id
        facts={'competition_id':'c09-computer-design','project_name':'新库单次上传验收','award_date':'2026-05-08','event_year':2026,'level':'national','award':'second','participation_mode':'individual'}
        original=next((ROOT/'samples'/'ComputerDesign').glob('*.jpg'))
        response=client.post('/api/materials/competition/records',data={'year':'2028','data':json.dumps(facts),'files':(io.BytesIO(original.read_bytes()),original.name)})
        assert response.status_code==201,response.json
        row=response.json;path=f"/api/materials/competition/records/{row['id']}"
        assert row['workflow_state']=='ocr_queued'
        if real_ocr:
            provider=PaddleProvider()
        else:
            class Provider:
                def predict(self,path):
                    lines=['中国大学生计算机设计大赛','参赛学生：测试学生','《新库单次上传验收》','二等奖','2026年5月8日']
                    return {'rec_texts':lines,'rec_scores':[.99]*len(lines),'rec_polys':[[[10,i*30],[500,i*30],[500,i*30+20],[10,i*30+20]] for i in range(len(lines))]}
            provider=Provider()
        assert run_one_ocr(app,provider)
        ready=client.get(path).json
        assert ready['workflow_state']=='ready_to_submit',ready
        assert ready['data']==row['data']
        submitted=client.post(path+'/submit',json={'version':ready['version']})
        assert submitted.status_code==200,submitted.json
        with client.session_transaction() as session:session['user_id']=teacher.id
        context=client.get(path+'/review-context')
        assert context.status_code==200,context.json
        command={'version':submitted.json['version'],'decision':'approve','comment':'API验收：已核对原件及申报条件','idempotency_key':'fresh-api-review','ocr_confirmed':True}
        reviewed=client.post(path+'/review',json=command)
        assert reviewed.status_code==200,reviewed.json
        with client.session_transaction() as session:session['user_id']=admin.id
        admin_result=client.get(path)
        assert admin_result.status_code==200 and admin_result.json['workflow_state']=='approved'
        assert MaterialRecord.query.count()==ScoreEntry.query.count()==1 and Application.query.count()==0
        result={'database':str(database),'real_ocr':real_ocr,'api_journey':['single_upload:201','queue_persisted','worker_completed','ready_to_submit','submit:200','teacher_context:200','teacher_approve:200','admin_read:200'],'record_id':row['id'],'score_entries':1,'legacy_applications':0,'assessment':ready['ocr_assessment'],'recognized_fields':ready['ocr_raw_terms']['report']['fields'],'browser_verified':False}
        output=database.with_suffix('.json');output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Fresh API journey passed; evidence:',output)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--database',type=Path,required=True);parser.add_argument('--real-ocr',action='store_true');args=parser.parse_args();run(args.database,args.real_ocr)
