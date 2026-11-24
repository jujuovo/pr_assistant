"""Reproducible local scale fixture and reconciliation; never a production loader.

Uses real material commands, reviews, score snapshots and Flask routes. Synthetic
PDF originals and login credentials are for local acceptance only. No OCR success
is fabricated: volunteer PDFs exercise the actual return/appeal/manual path.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import csv
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
PREFIX = 'scale28_'
PASSWORD = 'Scale2028!Test'
Q = Decimal('.0001')
D = Decimal


def q(value):
    return D(str(value)).quantize(Q, rounding=ROUND_HALF_UP)


def write_json(path, value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    temporary.replace(path)


def proof_pdf(label):
    # Valid one-page PDF, deliberately and visibly synthetic. No external assets.
    text = f'SYNTHETIC TEST ONLY - NOT A REAL CERTIFICATE / {label}'
    stream = f'BT /F1 12 Tf 35 760 Td ({text}) Tj ET'.encode('ascii')
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream']
    data = b'%PDF-1.4\n'
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n'
    pos = len(data)
    data += b'xref\n0 6\n0000000000 65535 f \n'
    data += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    return data + f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{pos}\n%%EOF'.encode()


def competition_expected(item, facts):
    # Independent transcription of policy pp.5-6. Does not call production scorer.
    category = item['category']
    if item['event_family'] in {'icpc', 'ccpc'}:
        category = 'A+' if facts.get('event_format') == 'world_final' else 'A'
    matrix = {'national': {'first_or_above': [30, 15, 10], 'second': [15, 10, 5], 'third': [10, 5, 2]},
              'provincial': {'first_or_above': [5, 2, 1], 'second': [2, 1, '.5']}}
    base = D(str(matrix[facts['level']][facts['award']][['A+', 'A', 'A-'].index(category)]))
    if facts['participation_mode'] == 'individual':
        divisor = 3
    elif item['competition_id'].startswith(('c01-', 'c02-', 'c03-')):
        divisor = 3 if facts['personal_rank'] == 1 else 4 if facts['personal_rank'] <= 3 else 5
    else:
        divisor = 3 if facts['team_size'] == 2 else min(facts['team_size'], 5)
    return q(base / divisor)


def expected_totals(records, academic_base):
    approved = [r for r in records if r['scored']]
    comps = [r for r in approved if r['category'] == 'competition']
    excluded = set()
    order = lambda r: (-D(r['candidate']), r['catalog_order'], r['facts']['award_date'], r['id'])
    # Independent grouping using submitted facts instead of stored hash/group keys.
    for key in [lambda r: 'csp' if r['family'] == 'csp' else ('unique', r['id']),
                lambda r: ('programming', r['facts']['event_year']) if r['family'] in {'icpc', 'ccpc'} else ('unique', r['id']),
                lambda r: (r['family'], r['facts']['event_year']),
                lambda r: r['facts']['project_name'].strip().casefold()]:
        groups = defaultdict(list)
        for r in comps:
            if r['id'] not in excluded:
                groups[key(r)].append(r)
        for rows in groups.values():
            excluded.update(r['id'] for r in sorted(rows, key=order)[1:])
    kept = sorted([r for r in comps if r['id'] not in excluded], key=order)[:3]
    competition = sum((D(r['candidate']) for r in kept), D(0))
    papers = [r for r in approved if r['category'] in {'research_paper', 'invention_patent'}]
    seen, c_count, research = set(), 0, D(0)
    for r in papers:
        if r['category'] == 'research_paper':
            f=r['facts']
            value=D({'A':10,'B':6,'C':1}[f['ccf_grade']]) if f.get('ccf_entry')==f['venue'] else D(0)
            if not f['indexed'] or f['proof_date']>'2028-08-31': value=D(0)
            authors=[a for a in f['authors'] if a!=f.get('mentor')]
            if len(authors)>1: value*=D('.8') if authors[0]==f['student_author'] else D('.2')
            r['candidate']=str(q(value))
    for r in sorted(papers, key=lambda r: (-D(r['candidate']), r['id'])):
        identity = r['category'], r['facts']['work_key'].casefold()
        if identity in seen or (r.get('ccf_c') and c_count >= 2) or not D(r['candidate']):
            continue
        seen.add(identity)
        c_count += bool(r.get('ccf_c'))
        research += D(r['candidate'])
    innovations = {}
    for r in approved:
        if r['category'] == 'innovation_training':
            identity = r['verified']['project_key']
            innovations[identity] = max(innovations.get(identity, D(0)), D(r['candidate']))
    innovation = min(sum(innovations.values(), D(0)), D(2))
    works = {}
    for r in approved:
        if r['category'] == 'student_work':
            year = r['verified']['assessments'][0]['academic_year']
            works[year] = max(works.get(year, D(0)), D(r['candidate']))
    work = min(sum(works.values(), D(0)), D(2))
    hours = sum((D(r['facts'].get('regular_hours', 0)) + D(r['facts'].get('reduced_hours', 0))/2
                 for r in approved if r['category'] == 'volunteer'), D(0))
    volunteer = min((max(hours-200, D(0)) // 2) * D('.05'), D(1))
    raw_a, raw_c = competition + research + innovation, work + volunteer
    a, c = min(raw_a, D(15)), min(raw_c, D(5))
    return {k: str(q(v)) for k, v in dict(academic_raw_total=raw_a, academic_total=a,
            comprehensive_raw_total=raw_c, comprehensive_total=c,
            score=D(str(academic_base))*D('.8')+a+c, competition=competition,
            research=research, innovation=innovation, student_work=work, volunteer=volunteer).items()}


def run(args):
    database = args.database_file.resolve()
    if os.environ.get('APP_ENV') == 'production' or database.parent != (BACKEND/'instance').resolve() or database.name == 'gradpush.db':
        raise ValueError('Only an explicitly selected local instance SQLite copy is allowed')
    if not database.is_file():
        raise ValueError('Prepare the local database first')
    policy_hash=hashlib.sha256((BACKEND.parent/'docs/policies/xmu-informatics-2025-02.pdf').read_bytes()).hexdigest()
    if policy_hash!='48a8e4de880b6239aa0090c5b76e2358a3e577731cc2d98fd19e6c28e5dc43c4':
        raise ValueError('Authoritative policy source hash changed; re-audit independent expectations first')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output/'environment.json').exists():
        previous=json.loads((output/'environment.json').read_text(encoding='utf-8'))
        if Path(previous['database']).resolve()!=database:
            raise ValueError('Output checkpoint belongs to a different database')
    backup = output/'before-seed.db'
    if not backup.exists():
        with sqlite3.connect(database) as source, sqlite3.connect(backup) as target:
            source.backup(target)
    os.environ['DATABASE_URL'] = 'sqlite:///' + database.as_posix()
    from app import app
    from extensions import db
    from models import User, Student, Faculty, Department, Major
    from material_models import MaterialRecord
    from workflow_models import CompetitionRulePackage, StudentScoreSnapshot, ScoreEntry
    from use_cases.materials import create_material, add_attachments, submit_material, review_material
    from use_cases.manual_materials import is_manual, submit_manual, review_manual
    from use_cases.competition_review import review_competition_material
    from use_cases.research_review import review_research, review_policy_material
    from use_cases.scoring import rebuild_student_snapshot
    from services.materials.schemas import normalize_innovation, normalize_student_work
    from domain.innovation_scoring import POLICY_VERSION as IP, candidate as innovation_candidate
    from domain.student_work_scoring import POLICY_VERSION as WP, candidate as work_candidate
    from use_cases.volunteer_materials import appeal_volunteer
    from services.volunteer_ocr import queue
    app.config['TESTING'] = True
    results_path = output/'students.json'
    results = json.loads(results_path.read_text(encoding='utf-8')) if results_path.exists() else []
    population=output/'population'
    population.mkdir(exist_ok=True)
    known={r['student_id'] for r in results}
    for path in sorted(population.glob('*.json')):
        record=json.loads(path.read_text(encoding='utf-8'))
        if record['student_id'] not in known: results.append(record)
    for record in results:
        record['expected']=expected_totals(record['records'],record['academic_base'])
        record['mismatches']={k:dict(expected=record['expected'][k],actual=v) for k,v in record['actual'].items() if D(record['expected'][k])!=D(v)}
    started = time.perf_counter()
    with app.app_context():
        admin = User.query.filter_by(username='admin001').one()
        teacher = User.query.filter_by(username='teacher001').one()
        if db.engine.url.database.replace('\\', '/') != database.as_posix():
            raise ValueError('Database selection mismatch')
        faculty = db.session.get(Faculty, admin.faculty_id)
        if faculty.name != '信息学院':
            raise ValueError('This matrix implements only the authoritative informatics policy')
        package = CompetitionRulePackage.query.filter_by(status='current', cycle_code=2028).one()
        catalog = package.snapshot['catalog']
        # Separate test department, four populated majors and one empty major.
        department = Department.query.filter_by(faculty_id=faculty.id, name='规模测试系（合成数据）').first()
        if not department:
            department = Department(faculty_id=faculty.id, name='规模测试系（合成数据）')
            db.session.add(department); db.session.flush()
        majors = []
        for i in range(5):
            name = f'规模测试专业{i+1}' if i < 4 else '规模测试空专业'
            major = Major.query.filter_by(department_id=department.id, name=name).first()
            if not major:
                major = Major(name=name, department_id=department.id)
                db.session.add(major); db.session.flush()
            majors.append(major)
        # Real teacher/admin passwords remain untouched; extra scoped test roles.
        prototype = User(username='hash-only'); prototype.set_password(PASSWORD)
        test_hash = prototype.password
        for role in ['teacher', 'admin']:
            username = PREFIX + role
            if not User.query.filter_by(username=username).first():
                db.session.add(User(username=username, name='千人测试'+role, role=role, status='active',
                                    password=test_hash, faculty_id=faculty.id, department_id=department.id))
        other_faculty = Faculty.query.filter_by(name='规模测试隔离学院').first()
        if not other_faculty:
            other_faculty = Faculty(name='规模测试隔离学院'); db.session.add(other_faculty); db.session.flush()
        if not User.query.filter_by(username=PREFIX+'outside').first():
            db.session.add(User(username=PREFIX+'outside', name='跨学院测试教师', role='teacher', status='active',
                                password=test_hash, faculty_id=other_faculty.id))
        db.session.commit()
        write_json(output/'environment.json', dict(database=str(database), backup=str(backup),
                    faculty_id=faculty.id, department_id=department.id, majors=[dict(id=m.id,name=m.name) for m in majors],
                    student_password=PASSWORD, prefix=PREFIX, package=package.package_id,
                    original_counts={t: sqlite3.connect(backup).execute('SELECT COUNT(*) FROM '+t).fetchone()[0]
                                     for t in ['student','user','material_record','score_entry']}))

        def make(user, category, facts, *, state='verified', candidate=0, verified=None, **metadata):
            row = create_material(user, category, {'year':2028, 'data':facts})
            add_attachments(user, row, row.version, [(f'{category}-{row.id}-TEST.pdf',
                proof_pdf(f'{user.student_id}-{category}-{row.id}'))], app.config['MATERIAL_STORAGE_FOLDER'])
            if state != 'draft':
                if category == 'volunteer':
                    queue(row, user, [])
                    appeal_volunteer(user, row, row.version, '合成PDF不支持OCR，申请人工核对测试工时')
                elif is_manual(row):
                    submit_manual(user, row, row.version)
                else:
                    submit_material(user, row, row.version)
                if state not in {'submitted', 'needs_ocr'}:
                    decision = 'verified' if state == 'verified' else state
                    payload = dict(version=row.version, decision=decision, comment='合成测试：已人工核对测试原件',
                                   idempotency_key=f'scale:{row.id}')
                    if category == 'competition':
                        payload['decision'] = 'approve' if state == 'verified' else 'return'
                        review_competition_material(teacher,row,payload)
                    elif category in {'research_paper','invention_patent'}:
                        review_research(teacher,row,{**payload,'verified_facts':verified or facts})
                    elif category == 'innovation_training':
                        review_policy_material(teacher,row,{**payload,'verified_facts':verified},IP,
                                               normalize_innovation,innovation_candidate,'project_key')
                    elif category == 'student_work':
                        review_policy_material(teacher,row,{**payload,'verified_facts':verified},WP,
                                               normalize_student_work,work_candidate,None)
                    elif is_manual(row):
                        review_manual(teacher,row,{k:v for k,v in payload.items() if k!='idempotency_key'})
                    else:
                        review_material(teacher,row,row.version,decision,payload['comment'],payload['idempotency_key'])
            return dict(id=row.id, category=category, status=row.status, facts=facts, verified=verified,
                        candidate=str(q(candidate)), scored=state=='verified' and category in
                        {'competition','research_paper','invention_patent','innovation_training','student_work','volunteer'},
                        **metadata)

        completed = {r['student_id'] for r in results}
        for i in range(1,args.students+1):
            sid = PREFIX+f'{i:04d}'
            if sid in completed:
                if not User.query.filter_by(username=sid).first():
                    raise ValueError('Checkpoint/database mismatch')
                continue
            if Student.query.filter_by(student_id=sid).first():
                raise ValueError(f'Unowned/incomplete account collision: {sid}')
            major = majors[(i-1)%4]
            base = [0,60,79.9999,80,89.9999,90,99.9999,100][(i//4)%8]
            name = f'测试学生{i:04d}'
            if i%50 == 0: name = '同名学生'
            if i%100 == 1: name = "测试·边界 O'Neil"
            scope = dict(faculty_id=faculty.id,department_id=department.id,major_id=major.id)
            student = Student(student_id=sid,student_name=name,academic_score=base,
                              gpa=None if i%9==0 else round(base/25,4),gender=['男','女',None][i%3],
                              cet4_score=[None,0,425,710][i%4],cet6_score=[None,424,425,710][i%4],**scope)
            db.session.add(student); db.session.flush()
            user = User(username=sid,name=name,password=test_hash,role='student',status='active',student_id=sid,**scope)
            db.session.add(user); db.session.flush()
            rows=[]
            # All 14 categories for every account. Three information-only legacy
            # categories have no official rule in this deployment: keep as drafts.
            rows.append(make(user,'academic',dict(term='2026秋',courses=[dict(course_code='CS101',course_name='数据结构',credits='3',score='90',full_score='100')]),state='draft'))
            rows.append(make(user,'language',dict(exam_name='CET6',language='英语',score='425',full_score='710',test_date='2026-06-15',certificate_no=sid+'-CET'),state='draft'))
            rows.append(make(user,'honor',dict(honor_name='校级优秀学生',honor_level='校级',issuer='合成测试学校',award_date='2026-06-01'),state='draft'))
            manual = [
                ('competition_evidence',dict(competition_name='测试目录外竞赛',award_level='一等奖',award_date='2026-06-01')),
                ('certification',dict(certification_name='测试认证',score='100',full_score='100',test_date='2026-06-01',certificate_no=sid+'-CERT')),
                ('social_practice',dict(document_type='practice_proof',team='测试实践队',period_as_printed='2026暑期')),
                ('research',dict(document_type='research_report',report_no=sid+'-REPORT',database='合成检索库'))]
            for j,(category,facts) in enumerate(manual):
                status=['verified','submitted','needs_correction','rejected'][(i+j)%4]
                rows.append(make(user,category,facts,state=status))
            for j,kind in enumerate(['arts_competition','performance','arts_honor','dorm_honor','fitness_test']):
                rows.append(make(user,'arts_sports',dict(document_type=kind,project_name='合成文体项目'+str(j),award_date='2026-06-01'),
                                 state=['verified','submitted','needs_correction','rejected','draft'][(i+j)%5]))
            # Five events per student: every catalog entry, team sizes/ranks,
            # provincial/national, repeated event stage and cross-event same work.
            indices=[(i-1)%len(catalog),0,8,27,9]
            for j,index in enumerate(indices):
                item=catalog[index]
                level='provincial' if 'provincial' in item['levels'] else 'national'
                if item['event_family']=='csp': level='national'
                award=['first_or_above','second'][i%2] if level=='provincial' else ['first_or_above','second','third'][i%3]
                facts=dict(competition_id=item['competition_id'],project_name=f'合成作品{i:04d}-{j}',
                           award_date=['2025-09-01','2028-08-31','2026-06-01'][i%3],event_year=2026+j%2,
                           level=level,award=award,participation_mode='individual')
                if i%3:
                    size=[2,3,4,5,6,20][i%6]
                    facts.update(participation_mode='team',team_size=size,personal_rank=min((i%5)+1,size))
                if item['event_family'] in {'icpc','ccpc'}: facts['event_format']='regional' if item['event_family']=='icpc' else 'national'
                if item['event_family']=='csp': facts['csp_percentile']={'first_or_above':'.2','second':'1.5','third':'3'}[award]
                if j==4 and i%7==0: facts['project_name']=f'合成作品{i:04d}-1'
                state='verified' if (i+j)%10<7 else 'submitted' if (i+j)%10==7 else 'needs_correction' if (i+j)%10==8 else 'draft'
                rows.append(make(user,'competition',facts,state=state,candidate=competition_expected(item,facts),
                                 family=item['event_family'],catalog_order=index))
            # CCF-C maximum two, duplicate work, high score cap, not indexed,
            # ineligible institution, deadline and author ordering.
            for j in range(3):
                grade=['A','B','C'][i%3]
                author=name
                facts=dict(title=f'合成测试论文{i}-{j}',work_key=f'doi:scale/{i}/{j}',first_institution='厦门大学',
                           authors=[author],student_author=author,venue='测试期刊',proof_date='2028-08-31',
                           published=True,indexed=True,article_type='full_article',cofirst_authors=[],
                           ccf_grade=grade,ccf_version='2025',ccf_entry='测试期刊',directory_basis='测试审核依据：模拟教师核定目录，不是真实科研证明')
                candidate={'A':10,'B':6,'C':1}[grade]
                if i%10==0 and j==1: facts['work_key']=f'doi:scale/{i}/0'
                if i%10==1 and j==2: facts['indexed']=False; candidate=0
                if i%10==2 and j==2: facts['proof_date']='2028-09-01'; candidate=0
                if i%10==3: facts['authors']=['合成导师',author]; facts['mentor']='合成导师'
                state=['verified','verified','submitted','needs_correction','rejected'][((i//10)+j)%5]
                rows.append(make(user,'research_paper',facts,state=state,candidate=candidate,ccf_c=grade=='C'))
            patent=dict(title='合成发明专利测试',work_key=f'CN-TEST-{i}',first_institution='厦门大学',
                        authors=[name],student_author=name,authorized_national_invention=i%4!=0,certificate_date='2028-08-31')
            rows.append(make(user,'invention_patent',patent,candidate=0 if i%4==0 else 2))
            for j in range(3):
                level=['national','provincial','university'][(i+j)%3]
                role='leader' if i%2 else 'member'
                facts=dict(project_name=f'合成创新项目{i}-{j}',project_number=f'TEST-{i}-{j}',level=level,role=role,
                           completed=i%8!=0,proof_type='academic_affairs',completion_date='2028-08-31')
                scores={'national':{'leader':1,'member':'.3'},'provincial':{'leader':'.5','member':'.2'},'university':{'leader':'.1','member':'.05'}}
                verified={**facts,'project_key':f'project-{i}-{0 if i%9==0 else j}','identity_basis':'人工核对测试项目编号'}
                rows.append(make(user,'innovation_training',facts,candidate=scores[level][role] if facts['completed'] else 0,verified=verified))
            for j in range(2):
                facts=dict(as_of='2028-08-31',appointments=[dict(organization='合成测试学生会',position='班长',
                           position_level='院级',start_date='2026-09-01',end_date='2027-08-31',assessment_result='待核定')])
                tenure=['below_semester','semester','full_year'][i%3]
                assessment=dict(appointment_index=0,academic_year=2026 if i%2 else 2026+j,mapped_position='班长',
                    mapping_basis='合成任命文件',scope='college',tenure=tenure,tenure_basis='人工核对测试任期',
                    assessment_score=str([0,60,99.99,100][i%4]),assessor_role='辅导员',assessment_source='合成考核表',proof_date='2028-08-31')
                candidate=D(assessment['assessment_score'])/100*[D(0),D('.5'),D(1)][i%3]
                rows.append(make(user,'student_work',facts,verified={'assessments':[assessment]},candidate=candidate))
            for j in range(2):
                hours=['0.01','99.99','100','100.5','101','119','120','150','500'][i%9]
                facts=dict(regular_hours=hours if j==0 else '0',reduced_hours='0' if j==0 else str(D(hours)*2),award_date='2026-06-01')
                state='verified' if i%5!=0 else 'submitted'
                rows.append(make(user,'volunteer',facts,state=state))
            snapshot,_=rebuild_student_snapshot(sid,2028)
            expected=expected_totals(rows,base)
            actual={k:str(getattr(snapshot,v)) for k,v in dict(academic_raw_total='specialty_raw_score',academic_total='specialty_score',
                    comprehensive_raw_total='performance_raw_score',comprehensive_total='performance_score',score='comprehensive_score').items()}
            result=dict(student_id=sid,name=name,major_id=major.id,academic_base=base,expected=expected,actual=actual,records=rows)
            result['mismatches']={k:dict(expected=expected[k],actual=v) for k,v in actual.items() if D(expected[k])!=D(v)}
            db.session.commit()
            results.append(result)
            write_json(population/(sid+'.json'),result)
            if i%25==0 or i==args.students:
                print(f'{i}/{args.students} students; materials={sum(len(r["records"]) for r in results)}; mismatches={sum(bool(r["mismatches"]) for r in results)}; seconds={time.perf_counter()-started:.1f}',flush=True)
        write_json(results_path,results)
        with (output/'accounts.csv').open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.writer(handle); writer.writerow(['username','password','name','role','major_id'])
            for r in results: writer.writerow([r['student_id'],PASSWORD,r['name'],'student',r['major_id']])
            for role in ['teacher','admin','outside']: writer.writerow([PREFIX+role,PASSWORD,'合成测试角色',role,''])
        return verify(app,db,results,output,faculty.id,department.id,majors)


def verify(app,db,results,output,faculty_id,department_id,majors):
    from models import User
    from workflow_models import ScoreEntry, StudentScoreSnapshot
    from material_models import MaterialRecord
    failures=[]
    checks=[]
    def check(name,condition,details=None):
        record=dict(name=name,passed=bool(condition),details=details)
        checks.append(record)
        if not condition: failures.append(record)
    check('all_expected_scores',not any(r['mismatches'] for r in results),[r['student_id'] for r in results if r['mismatches']])
    check('all_accounts_check_real_bcrypt_password',all(User.query.filter_by(username=r['student_id']).one().check_password(PASSWORD) for r in results))
    clients={}
    for role in ['teacher','admin','outside']:
        client=app.test_client()
        with client.session_transaction() as session: session['user_id']=User.query.filter_by(username=PREFIX+role).one().id
        clients[role]=client
    report_rows=[]
    for role in ['teacher','admin']:
        for major in majors:
            route=f'/api/workflow/teacher/score-report?faculty_id={faculty_id}&department_id={department_id}&major_id={major.id}&year=2028'
            tick=time.perf_counter(); response=clients[role].get(route); elapsed=time.perf_counter()-tick
            data=response.get_json()
            write_json(output/f'report-{role}-{major.id}.json',data)
            expected={r['student_id']:r for r in results if r['major_id']==major.id}
            rows=(data or {}).get('students',[])
            check(f'{role}_report_{major.id}_complete',response.status_code==200 and {r['student_id'] for r in rows}==set(expected) and len(rows)==len(expected),dict(status=response.status_code,rows=len(rows),seconds=elapsed))
            bad=[]
            for row in rows:
                if row['student_id'] not in expected: continue
                for field in ['academic_raw_total','academic_total','comprehensive_raw_total','comprehensive_total','score']:
                    if row.get(field) is None or D(row[field])!=D(expected[row['student_id']]['expected'][field]): bad.append([row['student_id'],field])
            check(f'{role}_report_{major.id}_scores',not bad,bad[:20])
            scored=sorted(rows,key=lambda row:D(row['score']),reverse=True)
            rank=0; previous=None
            for index,row in enumerate(scored,1):
                if D(row['score'])!=previous: rank=index; previous=D(row['score'])
                check(f'{role}_rank_{row["student_id"]}',row['report_rank']==rank)
            if role=='teacher': report_rows.extend(rows)
    sample=results[0]
    sid=sample['student_id']
    student_client=app.test_client()
    with student_client.session_transaction() as session: session['user_id']=User.query.filter_by(username=sid).one().id
    route=f'/api/workflow/teacher/score-report?faculty_id={faculty_id}&department_id={department_id}&major_id={majors[0].id}&year=2028'
    check('student_report_denied',student_client.get(route).status_code==403)
    check('cross_faculty_report_denied',clients['outside'].get(route).status_code==403)
    check('student_other_score_denied',student_client.get(f'/api/workflow/students/{results[1]["student_id"]}/score/current').status_code==403)
    for r in results:
        response=clients['teacher'].get(f'/api/workflow/students/{r["student_id"]}/score/current')
        body=response.get_json() or {}
        check(f'score_explanation_{r["student_id"]}',response.status_code==200 and D(str(body.get('comprehensive_score',-1)))==D(r['expected']['score']),dict(status=response.status_code))
    ids=[r['student_id'] for r in results]
    entries=ScoreEntry.query.filter(ScoreEntry.student_id.in_(ids)).all()
    by_material={e.material_record_id:e for e in entries if e.status=='active'}
    unexpected=[r['id'] for s in results for r in s['records'] if not r['scored'] and r['id'] in by_material]
    check('unreviewed_rejected_manual_never_scored',not unexpected,unexpected[:20])
    check('single_current_snapshot_per_student',StudentScoreSnapshot.query.filter(StudentScoreSnapshot.student_id.in_(ids),StudentScoreSnapshot.status=='current').count()==len(results))
    check('unique_material_score_source',len(by_material)==len([e for e in entries if e.status=='active']))
    # Actual ranking draft and audited export routes, never publish formal results.
    cutoff=datetime.now().isoformat()
    generated=clients['admin'].post('/api/workflow/rankings/generate',json=dict(year=2028,faculty_id=faculty_id,major_id=majors[0].id,
                         cutoff_at=cutoff,precision=4,idempotency_key='scale28-ranking-'+hashlib.sha256(cutoff.encode()).hexdigest()[:20]))
    ranking=generated.get_json() or {}
    write_json(output/'ranking.json',ranking)
    check('ranking_generation',generated.status_code==201,dict(status=generated.status_code,body=ranking if generated.status_code!=201 else None))
    if generated.status_code==201:
        batch_id=ranking['batch_id']
        exported=clients['admin'].post(f'/api/workflow/rankings/{batch_id}/export',json={'purpose':'千人规模测试核对'})
        write_json(output/'ranking-export.json',exported.get_json())
        check('ranking_export',exported.status_code==200,dict(status=exported.status_code))
    write_json(output/'report-rows.json',report_rows)
    summary=dict(database=os.environ['DATABASE_URL'],students=len(results),materials=sum(len(r['records']) for r in results),
        categories=Counter(r['category'] for s in results for r in s['records']),states=Counter(r['status'] for s in results for r in s['records']),
        checks=len(checks),passed=len(checks)-len(failures),failures=failures,score_mismatches=[{k:v for k,v in r.items() if k!='records'} for r in results if r['mismatches']],
        limitations=['Flask test-client routes, not live TCP HTTP; host network socket access unavailable',
                     'Sequential integration volume, not concurrency/latency SLA', 'Real browser rendering and download require user acceptance',
                     'Synthetic PDFs; real OCR success not covered', 'SQLite only; production dialect/migration not exercised',
                     'academic/language/honor kept as drafts because no authoritative material rule is available'])
    write_json(output/'checks.json',checks)
    write_json(output/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in {'score_mismatches','limitations'}},ensure_ascii=True),flush=True)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-file',type=Path,required=True)
    parser.add_argument('--students',type=int,default=1000)
    parser.add_argument('--output',type=Path,default=BACKEND/'outputs/thousand-students')
    outcome=run(parser.parse_args())
    sys.exit(1 if outcome['failures'] else 0)
