"""材料归属、版本控制、校方快照和一致性比较；不调用评分引擎。"""
import hashlib
import json
from pathlib import Path
from flask import abort, current_app, session
from extensions import db
from models import Application, Student, User
from material_models import MaterialRecord, MaterialEvent, MaterialSource
from automation_models import utcnow
from services.automation import actor
from .schemas import TYPES, integer, normalize, analyze, text, source_url, object_keys


def has_linked_material(application_id):
    return MaterialRecord.query.filter_by(application_id=application_id).first() is not None


def scope_application_query(query):
    """旧申请列表中，关联新材料的申请同样遵循本人/同院权限。"""
    from sqlalchemy import or_
    protected = Application.id.in_(db.session.query(MaterialRecord.application_id).filter(
        MaterialRecord.application_id.isnot(None)))
    user = db.session.get(User, session.get('user_id')) if session.get('user_id') else None
    allowed = False
    if user and user.status == 'active':
        if user.role == 'student' and user.student_id:
            allowed = Application.student_id == user.student_id
        elif user.role in ('teacher', 'admin') and user.faculty_id:
            allowed = Application.faculty_id == user.faculty_id
    return query.filter(or_(~protected, allowed))


def category_exists(category):
    if category not in TYPES:
        abort(404, description='没有该材料类别')


def body():
    from flask import request
    result = request.get_json(silent=True)
    if not isinstance(result, dict):
        abort(400, description='请求体必须为JSON对象')
    return result


def authorize(row, user=None, staff=False):
    user = user or actor()
    if not staff and user.role == 'student' and row.student_id == user.student_id:
        return user
    if user.role in ('teacher','admin') and user.faculty_id and user.faculty_id == row.faculty_id:
        return user
    abort(403, description='没有该学生或学院的材料权限')


def record_at(category, record_id):
    category_exists(category)
    row = db.get_or_404(MaterialRecord,record_id)
    if row.category != category:
        abort(404, description='材料不属于此类别')
    authorize(row)
    return row


def version_change(row, version, allowed, changes):
    integer(version,'version',1,2_000_000_000)
    changed = MaterialRecord.query.filter_by(id=row.id,version=version).filter(MaterialRecord.status.in_(allowed)).update(
        {**changes,'version':MaterialRecord.version+1,'updated_at':utcnow()},synchronize_session=False)
    if not changed:
        abort(409,description='材料状态或版本已变化，请刷新后重试')
    db.session.refresh(row)


def event(row, action, details):
    db.session.add(MaterialEvent(record_id=row.id,actor_id=actor().id,action=action,details=details))


def view(row):
    return {'id':row.id, 'category':row.category, 'student_id':row.student_id, 'faculty_id':row.faculty_id,
            'application_id':row.application_id, 'year':row.year, 'status':row.status, 'version':row.version,
            'data':row.data, 'analysis':row.analysis, 'check_report':row.check_report,
            'recognition_status':'not_implemented', 'bonus_result':None,
            'created_at':row.created_at.isoformat()+'Z', 'updated_at':row.updated_at.isoformat()+'Z',
            'attachments':[{'id':f.id,'filename':f.filename,'size':f.size,'sha256':f.sha256,
                            'url':f'/api/materials/{row.category}/records/{row.id}/attachments/{f.id}'} for f in row.attachments]}


def make_record(category, data):
    category_exists(category)
    object_keys(data,{'year','data','application_id'},{'year','data'})
    user = actor()
    if user.role != 'student' or not user.student_id:
        abort(403,description='仅学生本人可创建申报材料')
    owner = Student.query.filter_by(student_id=user.student_id).first()
    if not owner or not owner.faculty_id or owner.faculty_id != user.faculty_id:
        abort(400,description='学生账号未正确关联学院')
    application_id = data.get('application_id')
    if application_id is not None:
        integer(application_id,'application_id',1,2_000_000_000)
        application = Application.query.filter_by(id=application_id).with_for_update().first_or_404()
        if application.student_id != user.student_id or application.faculty_id != owner.faculty_id:
            abort(403,description='不能关联其他学生的申请')
    normalized = normalize(category,data['data'])
    row = MaterialRecord(student_id=user.student_id,faculty_id=owner.faculty_id,category=category,
                         year=integer(data['year'],'year',2000,2100),application_id=application_id,
                         data=normalized,analysis=analyze(category,normalized),status='draft')
    db.session.add(row)
    db.session.flush()
    event(row,'created',{'version':1})
    return row


def storage_root():
    return Path(current_app.config.get('MATERIAL_STORAGE_FOLDER',Path(__file__).resolve().parents[2]/'private-evidence')).resolve()


def stored_path(name):
    root = storage_root()
    path = (root/name).resolve()
    if path.parent != root or path == root:
        abort(404,description='无效材料路径')
    return path


def check(row):
    reference = row.data.get('reference_id')
    report = {'status':'awaiting_official_data', 'authenticity':'not_assessed', 'source':None,
              'differences':[], 'message':'未提供可匹配的校方数据记录编号，请人工核验或由管理员导入数据。'}
    if not reference:
        return report
    source = MaterialSource.query.filter_by(faculty_id=row.faculty_id,student_id=row.student_id,
        category=row.category,year=row.year,external_id=reference).order_by(MaterialSource.revision.desc()).first()
    if not source:
        report['message']='没有找到同学院、同学生、同年度的来源数据；不能据此判定材料为假。'
        return report
    # 兼容旧记录缺少可选空字段，保持原始快照和摘要不变。
    claimed = normalize(row.category, row.data)
    official = normalize(row.category, source.data)
    left = {k:v for k,v in claimed.items() if k not in ('reference_id', 'project_key')}
    right = {k:v for k,v in official.items() if k not in ('reference_id', 'project_key')}
    differences = [{'field':k,'claimed':left.get(k),'source_value':right.get(k)}
                   for k in sorted(set(left)|set(right)) if left.get(k) != right.get(k)]
    report.update(status='consistent' if not differences else 'mismatch', differences=differences,
                  source={'id':source.id,'external_id':source.external_id,'revision':source.revision,
                          'name':source.source_name,'url':source.source_url,'digest':source.digest},
                  message='申报字段与管理员录入的数据一致，仍需核验来源与认定条件。' if not differences else '申报字段与来源数据存在差异，请人工核对。')
    return report


def import_sources(payload):
    user=actor()
    if user.role != 'admin' or not user.faculty_id:
        abort(403,description='仅本学院管理员可录入来源数据')
    object_keys(payload,{'source_name','source_url','records'},{'source_name','records'})
    name=text(payload['source_name'],'来源名称')
    url=source_url(payload.get('source_url',''))
    records=payload['records']
    if not isinstance(records,list) or not 1<=len(records)<=500:
        raise ValueError('一次导入必须包含1至500条记录')
    created,unchanged=[],[]
    for item in records:
        object_keys(item,{'student_id','category','year','external_id','revision','data'},
                    {'student_id','category','year','external_id','data'})
        category=item['category']
        if not isinstance(category,str) or category not in TYPES:
            raise ValueError('来源材料类别无效')
        student_id=text(item['student_id'],'student_id',maximum=20)
        student=Student.query.filter_by(student_id=student_id).first()
        if not student or student.faculty_id != user.faculty_id:
            abort(403,description='来源数据含非本学院学生，整批未导入')
        normalized=normalize(category,item['data'])
        year=integer(item['year'],'year',2000,2100)
        external_id=text(item['external_id'],'external_id',maximum=128)
        revision=integer(item.get('revision',1),'revision',1,2_000_000_000)
        digest=hashlib.sha256(json.dumps({'data':normalized,'source_name':name,'source_url':url},
                              sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()
        previous=MaterialSource.query.filter_by(faculty_id=user.faculty_id,student_id=student_id,category=category,
                     year=year,external_id=external_id,revision=revision).first()
        if previous:
            if previous.digest != digest:
                abort(409,description='同一来源版本的数据不能覆盖；请提高revision以保留历史快照')
            unchanged.append(previous.id)
            continue
        source=MaterialSource(faculty_id=user.faculty_id,student_id=student_id,category=category,year=year,
                             external_id=external_id,revision=revision,source_name=name,source_url=url,
                             data=normalized,digest=digest,imported_by=user.id)
        db.session.add(source)
        db.session.flush()
        created.append(source.id)
    return {'created_ids':created,'unchanged_ids':unchanged,'created_count':len(created),'unchanged_count':len(unchanged),
            'note':'只保存管理员提供的来源快照，没有连接外部学校平台，也没有认定真实性或加分。'}
