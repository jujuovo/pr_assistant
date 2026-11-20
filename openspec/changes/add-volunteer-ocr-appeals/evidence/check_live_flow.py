"""Real local HTTP + fresh SQLite + PP-OCRv5; no browser automation."""
import argparse
import json
import uuid
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import requests

ROOT=Path(__file__).resolve().parents[4]
BACKEND=ROOT/'backend'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--database-file',type=Path)
parser.add_argument('--platform-sample',type=Path)
parser.add_argument('--platform-all',action='store_true')
parser.add_argument('--font',type=Path,default=Path('C:/Windows/Fonts/msyh.ttc'))
args=parser.parse_args()
DATABASE=(args.database_file or BACKEND/'instance'/('volunteer-acceptance-'+uuid.uuid4().hex[:8]+'.db')).resolve()
OUTPUT=BACKEND/'outputs/volunteer-ocr'
BASE='http://127.0.0.1:5002'
os.environ['DATABASE_URL']='sqlite:///'+DATABASE.as_posix()
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK']='True'
sys.path.insert(0,str(BACKEND))
trace=[]


def call(session, method, route, expected=200, **kwargs):
    response=session.request(method,BASE+route,timeout=60,**kwargs)
    trace.append({'method':method,'path':route,'status':response.status_code})
    assert response.status_code==expected,(route,response.status_code,response.text[:1000])
    return response.json()


def login(username):
    session=requests.Session()
    captcha=call(session,'GET','/api/generate-captcha')
    # Read only this isolated development fixture; do not bypass auth or log captcha/password.
    with sqlite3.connect(DATABASE) as connection:
        text=connection.execute('SELECT text FROM captcha WHERE token=?',(captcha['token'],)).fetchone()[0]
    call(session,'POST','/api/login',json={'username':username,'password':'demo123','captcha':text,'captchaToken':captcha['token']})
    return session


def upload(session, hours, proof=None, day="2026-05-08"):
    proof=proof or OUTPUT/'synthetic-volunteer-proof.png'
    with proof.open('rb') as stream:
        return call(session,'POST','/api/materials/volunteer/records',201,
                    data={'year':'2028','data':json.dumps({'regular_hours':hours,'reduced_hours':'0','award_date':day})},
                    files={'files':('proof.png',stream,'image/png')})


SCREEN_CASES = {
    'example1.jpg': ('12', '2026-09-14', 'honor'),
    'example2.jpg': ('5.05', '2025-12-21', 'credit'),
    'example3.jpg': ('11.5', '2026-09-18', 'honor'),
    'example4.jpg': ('0.94', '2026-04-06', 'credit'),
    'example5.jpg': ('3.42', '2026-11-06', 'credit'),
    'example6.jpg': ('3.2', '2026-11-06', 'credit'),
    'example7.jpg': ('5.02', '2025-12-09', 'honor'),
}


def check_platform_screens(student,app,provider,run_one_ocr):
    files=sorted((BACKEND/'samples/VolunteerHours').glob('*.jpg')) if args.platform_all else [args.platform_sample] if args.platform_sample else []
    checks=[]
    for source in files:
        hours,day,kind=SCREEN_CASES[source.name]
        sample=upload(student,hours,source,day)
        with app.app_context():assert run_one_ocr(app,provider)
        checked=call(student,'GET',f"/api/materials/volunteer/records/{sample['id']}")
        values={item['field']:item for item in checked['volunteer_ocr']['comparisons']}
        assert len(values)==3 and all(item['matches'] for item in values.values()),(source.name,values)
        assert values['hours']['recognized']==hours
        assert values['service_type']['recognized']=='普通志愿服务' and values['award_date']['recognized']==day
        assert checked['workflow_state']=='ready_to_submit' and 'submit' in checked['allowed_actions']
        report=checked['ocr_raw_terms']['reports'][0]['report']
        assert report['platform_policy']['page_type']==kind and report['missing_fields']==[]
        item={'file':source.name,'hours':hours,'service_type':'regular','date':day,'page_type':kind,
              'comparisons':list(values.values()),'status':checked['workflow_state']}
        checks.append(item)
        print(json.dumps({'platform_passed':source.name,'all_three_match':True}),flush=True)
    if args.platform_all:assert len(checks)==7
    return checks


def main():
    assert not DATABASE.exists(), 'Choose a new database path; existing data is never deleted'
    assert args.font.is_file(), 'Provide a Chinese font with --font'
    OUTPUT.mkdir(parents=True,exist_ok=True)
    subprocess.run([sys.executable,'-B',str(BACKEND/'tools/prepare_local.py'),'--database-file',str(DATABASE)],cwd=ROOT,check=True)
    from PIL import Image, ImageDraw, ImageFont
    image=Image.new('RGB',(1600,650),'white')
    draw=ImageDraw.Draw(image);font=ImageFont.truetype(str(args.font),48)
    for index,line in enumerate(['志愿服务工时证明','本次工时：202小时','工时类别：普通志愿服务','系统录入并审核通过日期：2026年5月8日']):
        draw.text((70,60+index*135),line,font=font,fill='#172b4d')
    image.save(OUTPUT/'synthetic-volunteer-proof.png')
    with sqlite3.connect(DATABASE) as connection:
        assert connection.execute("SELECT COUNT(*) FROM material_record WHERE category='volunteer'").fetchone()[0]==0,'Use a newly prepared acceptance database'
    env={**os.environ,'PYTHONUTF8':'1'}
    server_log=(OUTPUT/'live-server.log').open('w',encoding='utf-8')
    server=subprocess.Popen([sys.executable,'-B','-c','from app import app; app.run(port=5002,debug=False,use_reloader=False)'],cwd=BACKEND,env=env,stdout=server_log,stderr=server_log,
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        for _ in range(40):
            try:
                if requests.get(BASE+'/api/public/system-info',timeout=1).status_code==200:break
            except requests.RequestException:pass
            time.sleep(.25)
        else:raise AssertionError('live backend not ready')
        from app import app
        from services.recognition.provider import PaddleProvider
        from services.competition_ocr.worker import run_one_ocr
        from extensions import db
        from workflow_models import ScoreEntry
        provider=PaddleProvider(model_root=BACKEND/'ocr-models')
        student=login('student001')
        first=upload(student,'202');first_path=f"/api/materials/volunteer/records/{first['id']}"
        assert first['workflow_state']=='ocr_queued'
        with app.app_context():assert run_one_ocr(app,provider)
        completed=call(student,'GET',first_path)
        assert completed['volunteer_ocr']['status']=='matched',completed['volunteer_ocr']
        submitted=call(student,'POST',first_path+'/submit',json={'version':completed['version']})
        second=upload(student,'203');second_path=f"/api/materials/volunteer/records/{second['id']}"
        with app.app_context():assert run_one_ocr(app,provider)
        returned=call(student,'GET',second_path)
        assert returned['volunteer_ocr']['status']=='returned'
        appealed=call(student,'POST',second_path+'/appeal',json={'version':returned['version'],'reason':'测试申诉：请教师核对工时原件，原申报保留。'})
        assert appealed['priority_review'] and appealed['status']=='submitted'
        platform_check=check_platform_screens(student,app,provider,run_one_ocr)
        reviewer=login('teacher001')
        pending=call(reviewer,'GET','/api/materials/volunteer/records')['records']
        assert next(row for row in pending if row['id']==second['id'])['priority_review']
        approved=call(reviewer,'POST',first_path+'/review',json={'version':submitted['version'],'decision':'verified','comment':'','idempotency_key':'live-volunteer-pass'})
        assert approved['status']=='scored'
        rejected=call(reviewer,'POST',second_path+'/review',json={'version':appealed['version'],'decision':'rejected','comment':'申诉人工核对：原件202小时，申报203小时不符。','idempotency_key':'live-volunteer-reject'})
        assert rejected['status']=='rejected' and rejected['priority_review']
        with app.app_context():
            entries=ScoreEntry.query.filter_by(status='active',category='volunteer').all()
            assert len(entries)==1 and str(entries[0].effective_score)=='0.0500'
            db.session.remove()
        report={'passed':True,'database':str(DATABASE),'model':'PP-OCRv5_mobile','trace':trace,'matched_record':first['id'],'appealed_record':second['id'],'active_score':'0.0500','platform_sample':platform_check,'browser':'not executed; user manual only'}
        (OUTPUT/'live-http-evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'passed':True,'requests':len(trace),'real_model_jobs':2+len(platform_check),'active_score':'0.0500'}))
    finally:
        server.terminate();server.wait(timeout=15);server_log.close()


if __name__=='__main__':main()
