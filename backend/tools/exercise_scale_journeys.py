"""Real-route cap, correction, duplicate and withdrawal journeys on a separate major."""
from pathlib import Path
import argparse
import copy
from decimal import Decimal
from io import BytesIO
import json
import os
import sys

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from tools.exercise_thousand_students import PASSWORD,PREFIX,proof_pdf,write_json


def run(output,resume_initial=False):
    env=json.loads((output/'environment.json').read_text(encoding='utf-8'))
    fixture=json.loads((output/'students.json').read_text(encoding='utf-8'))[0]
    database=Path(env['database']).resolve()
    if os.environ.get('APP_ENV')=='production' or database.parent!=(BACKEND/'instance').resolve() or database.name=='gradpush.db':
        raise ValueError('Local test database required')
    os.environ['DATABASE_URL']='sqlite:///'+database.as_posix()
    from app import app
    from extensions import db
    from models import User,Student,Major
    from material_models import MaterialRecord
    from workflow_models import ScoreEntry
    app.config['TESTING']=True
    checks=[]
    def check(name,condition,**details):
        checks.append(dict(name=name,passed=bool(condition),**details))
        if not condition: raise AssertionError(checks[-1])
    with app.app_context():
        username=PREFIX+'journey'
        existing=User.query.filter_by(username=username).first()
        if existing:
            if (output/'journeys.json').exists():
                return json.loads((output/'journeys.json').read_text(encoding='utf-8'))
            first=MaterialRecord.query.filter_by(student_id=username).all()
            if not resume_initial or len(first)!=1 or first[0].category!='academic' or first[0].status!='draft' or first[0].attachments:
                raise ValueError('Incomplete journey exists; inspect rather than silently overwrite')
            initial=first[0]
            user=existing;student=Student.query.filter_by(student_id=username).one();major=db.session.get(Major,student.major_id)
        else:
            initial=None
            major=Major(name='规模测试边界专业',department_id=env['department_id'])
            db.session.add(major);db.session.flush()
            scope=dict(faculty_id=env['faculty_id'],department_id=env['department_id'],major_id=major.id)
            student=Student(student_id=username,student_name='封顶与补正链测试',academic_score=80,gpa=3.2,**scope)
            db.session.add(student);db.session.flush()
            user=User(username=username,name=student.student_name,role='student',status='active',student_id=username,**scope)
            user.set_password(PASSWORD);db.session.add(user);db.session.commit()
        student_client=app.test_client();teacher_client=app.test_client()
        with student_client.session_transaction() as session:session['user_id']=user.id
        with teacher_client.session_transaction() as session:session['user_id']=User.query.filter_by(username=PREFIX+'teacher').one().id
        def request(client,method,path,allowed=(200,),**kwargs):
            response=getattr(client,method)(path,**kwargs)
            check(method+' '+path,response.status_code in allowed,status=response.status_code)
            return response.get_json()
        sequence=0
        def create(category,facts):
            nonlocal sequence
            sequence+=1
            path=f'/api/materials/{category}/records'
            row=request(student_client,'get',path+'/'+str(initial.id)) if initial is not None and sequence==1 else request(student_client,'post',path,allowed=(201,),json={'year':2028,'data':facts})
            return request(student_client,'post',f'{path}/{row["id"]}/attachments',allowed=(200,201),data={
                'version':str(row['version']),'files':(BytesIO(proof_pdf('BOUNDARY-'+str(sequence))),'BOUNDARY-TEST.pdf')})
        def submit(category,row):
            return request(student_client,'post',f'/api/materials/{category}/records/{row["id"]}/submit',json={'version':row['version']})
        def review(category,row,facts=None,decision='verified'):
            payload=dict(version=row['version'],decision=decision,comment='合成测试：核对封顶与补正',idempotency_key='journey-'+str(row['id'])+'-'+str(row['version']))
            if facts is not None:payload['verified_facts']=facts
            return request(teacher_client,'post',f'/api/materials/{category}/records/{row["id"]}/review',json=payload)
        rows=[]; papers=[]
        # Ensure every category is represented in this account as well.
        extras=['academic','language','honor','competition_evidence','certification','social_practice','research','arts_sports']
        for category in extras:
            facts=copy.deepcopy(next(r['facts'] for r in fixture['records'] if r['category']==category))
            rows.append(create(category,facts))
        for j in range(3):
            facts=dict(project_name=f'封顶创新项目{j}',project_number=f'EDGE-{j}',level='national',role='leader',completed=True,
                       proof_type='academic_affairs',completion_date='2028-08-31')
            row=submit('innovation_training',create('innovation_training',facts))
            rows.append(review('innovation_training',row,facts|{'project_key':f'EDGE-{j}','identity_basis':'合成项目编号'}))
        paper=copy.deepcopy(next(r['facts'] for r in fixture['records'] if r['category']=='research_paper'))
        for j in range(3):
            facts=paper|dict(title=f'封顶C类论文{j}',work_key=f'edge-c-{j}',venue='合成CCF-C条目',ccf_entry='合成CCF-C条目',ccf_grade='C',
                            authors=[student.student_name],student_author=student.student_name,indexed=True,published=True,proof_date='2028-08-31')
            row=submit('research_paper',create('research_paper',facts))
            result=review('research_paper',row,facts);rows.append(result);papers.append((result,facts))
        patent=dict(title='封顶测试合成专利',work_key='edge-patent',first_institution='厦门大学',authors=[student.student_name],
                    student_author=student.student_name,authorized_national_invention=True,certificate_date='2028-08-31')
        row=submit('invention_patent',create('invention_patent',patent))
        patent_result=review('invention_patent',row,patent);rows.append(patent_result)
        first_comp=None
        for j,competition_id in enumerate(['c01-china-college-student-innovation','c02-challenge-cup-academic','c03-challenge-cup-business-plan']):
            facts=dict(competition_id=competition_id,project_name=f'封顶竞赛作品{j}',award_date='2028-08-31',event_year=2026+j,
                       level='national',award='first_or_above',participation_mode='individual')
            row=submit('competition',create('competition',facts))
            result=review('competition',row,decision='approve');rows.append(result)
            if j==0:first_comp=(result,facts)
        work=copy.deepcopy(next(r['facts'] for r in fixture['records'] if r['category']=='student_work'))
        for j in range(3):
            row=submit('student_work',create('student_work',work))
            assessment=dict(appointment_index=0,academic_year=2025+j,mapped_position='院学生会执行主席',mapping_basis='合成任命文件',scope='college',
                            tenure='full_year',tenure_basis='完整学年证明',assessment_score='100',assessor_role='辅导员',assessment_source='合成考核表',proof_date='2028-08-31')
            rows.append(review('student_work',row,{'assessments':[assessment]}))
        facts=dict(regular_hours='240',reduced_hours='0',award_date='2028-08-31')
        row=create('volunteer',facts)
        row=request(student_client,'post',f'/api/materials/volunteer/records/{row["id"]}/ocr',allowed=(202,),json={'version':row['version']})
        row=request(student_client,'post',f'/api/materials/volunteer/records/{row["id"]}/appeal',json={'version':row['version'],'reason':'合成PDF人工核对240小时'})
        rows.append(review('volunteer',row))
        def totals(academic_raw):
            result=request(student_client,'get',f'/api/workflow/students/{username}/score/current')
            check('independent_total_82',Decimal(result['comprehensive_score'])==82,actual=result['comprehensive_score'])
            check('academic_raw_'+str(academic_raw),Decimal(result['categories']['academic']['raw_score'])==academic_raw)
            return result
        baseline=totals(36)
        # Correction of a counted C paper activates the former third paper.
        source,facts=papers[0]
        successor=request(student_client,'post',f'/api/materials/research_paper/records/{source["record_id"]}/corrections',allowed=(201,),
                          json={'version':source['version'],'confirmed_terms':facts})
        successor=request(student_client,'post',f'/api/materials/research_paper/records/{successor["id"]}/attachments',allowed=(200,201),data={
            'version':str(successor['version']),'files':(BytesIO(proof_pdf('CORRECTION-C')),'CORRECTION-TEST.pdf')})
        successor=submit('research_paper',successor)
        rows.append(review('research_paper',successor,facts|{'indexed':False}))
        totals(36)
        check('old_c_score_invalidated',ScoreEntry.query.filter_by(material_record_id=source['record_id']).one().status=='invalidated')
        # Patent correction removes two raw points despite the visible total
        # remaining capped. This catches implementations that only compare totals.
        successor=request(student_client,'post',f'/api/materials/invention_patent/records/{patent_result["record_id"]}/corrections',allowed=(201,),
                          json={'version':patent_result['version'],'confirmed_terms':patent})
        successor=request(student_client,'post',f'/api/materials/invention_patent/records/{successor["id"]}/attachments',allowed=(200,201),data={
            'version':str(successor['version']),'files':(BytesIO(proof_pdf('CORRECTION-P')),'CORRECTION-TEST.pdf')})
        successor=submit('invention_patent',successor)
        rows.append(review('invention_patent',successor,patent|{'authorized_national_invention':False}))
        final=totals(34)
        # Exact duplicate submit is rejected; the draft remains reviewable.
        duplicate=create('competition',first_comp[1])
        response=student_client.post(f'/api/materials/competition/records/{duplicate["id"]}/submit',json={'version':duplicate['version']})
        check('exact_duplicate_blocked',response.status_code==409,status=response.status_code)
        # Withdrawal + return/correction version chain on a distinct competition.
        facts=first_comp[1]|{'project_name':'撤回及补正测试作品','event_year':2025}
        row=submit('competition',create('competition',facts))
        row=request(student_client,'post',f'/api/materials/competition/records/{row["id"]}/withdraw',json={'version':row['version']})
        row=submit('competition',row)
        returned=review('competition',row,decision='return')
        successor=request(student_client,'post',f'/api/materials/competition/records/{row["id"]}/corrections',allowed=(201,),
                          json={'version':returned['version'],'confirmed_terms':facts|{'project_name':'撤回及补正测试作品-已修正'}})
        successor=submit('competition',successor)
        rows.append(review('competition',successor,decision='approve'))
        totals(34)
        result=dict(username=username,password=PASSWORD,major_id=major.id,checks=checks,
                    materials=MaterialRecord.query.filter_by(student_id=username).count(),
                    final_expected=dict(academic_raw_total='34.0000',academic_total='15.0000',comprehensive_total='3.0000',score='82.0000'),
                    final_score=final['comprehensive_score'],passed=all(c['passed'] for c in checks))
        write_json(output/'journeys.json',result)
        print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=BACKEND/'outputs/thousand-students')
    parser.add_argument('--resume-initial',action='store_true',help='Resume only an inspected, empty initial academic draft after an interrupted upload')
    args=parser.parse_args()
    run(args.output.resolve(),args.resume_initial)
