"""五类材料接口。申报、附件、结构化导入和核验可用，OCR/自动加分明确未启用。"""
import csv
import hashlib
import io
from pathlib import Path
import uuid
from flask import Blueprint, abort, current_app, jsonify, request, send_file
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException
from extensions import db
from material_models import MaterialRecord, MaterialAttachment, MaterialSource
from services.automation import actor
from services.materials.schemas import (TYPES, type_view, normalize, analyze, integer, text, object_keys)
from services.materials.service import (body, record_at, category_exists, authorize, make_record, view,
                                       version_change, event, stored_path, check, import_sources)

material_bp=Blueprint('materials',__name__,url_prefix='/api/materials')


@material_bp.errorhandler(HTTPException)
def http_error(error):
    db.session.rollback()
    return jsonify({'error':error.description}),error.code


@material_bp.errorhandler(ValueError)
def invalid(error):
    db.session.rollback()
    return jsonify({'error':str(error)}),400


@material_bp.errorhandler(IntegrityError)
def conflict(error):
    db.session.rollback()
    return jsonify({'error':'记录发生并发冲突，整批未保存，请刷新重试'}),409


@material_bp.get('/types')
def types():
    actor()
    return jsonify(type_view())


@material_bp.route('/<category>/records',methods=['GET','POST'])
def records(category):
    category_exists(category)
    user=actor()
    if request.method=='POST':
        row=make_record(category,body())
        db.session.commit()
        return jsonify(view(row)),201
    query=MaterialRecord.query.filter_by(category=category)
    if user.role=='student':
        query=query.filter_by(student_id=user.student_id)
    elif user.role in ('teacher','admin') and user.faculty_id:
        query=query.filter_by(faculty_id=user.faculty_id)
    else:
        abort(403)
    for name in ('student_id','status'):
        if request.args.get(name):
            query=query.filter(getattr(MaterialRecord,name)==request.args[name])
    if request.args.get('year'):
        query=query.filter_by(year=integer(int(request.args['year']),'year',2000,2100))
    limit=integer(int(request.args.get('limit','50')),'limit',1,100)
    after=integer(int(request.args.get('after_id','0')),'after_id',0,2_000_000_000)
    rows=query.filter(MaterialRecord.id>after).order_by(MaterialRecord.id).limit(limit+1).all()
    return jsonify({'records':[view(row) for row in rows[:limit]],'next_after_id':rows[limit-1].id if len(rows)>limit else None})


@material_bp.route('/<category>/records/<int:record_id>',methods=['GET','PATCH'])
def record(category,record_id):
    row=record_at(category,record_id)
    if request.method=='GET':
        return jsonify(view(row))
    user=actor()
    if user.role!='student' or user.student_id!=row.student_id:
        abort(403,description='仅学生本人可修改申报字段')
    payload=body()
    object_keys(payload,{'version','data'},{'version','data'})
    normalized=normalize(category,payload['data'])
    version_change(row,payload['version'],['draft','needs_correction'],
                   {'data':normalized,'analysis':analyze(category,normalized),'check_report':None,'status':'draft'})
    event(row,'edited',{'version':row.version,'data':normalized})
    db.session.commit()
    return jsonify(view(row))


@material_bp.post('/<category>/records/<int:record_id>/submit')
def submit(category,record_id):
    row=record_at(category,record_id)
    if actor().role!='student':
        abort(403,description='仅学生本人可提交材料')
    payload=body(); object_keys(payload,{'version'},{'version'})
    version_change(row,payload['version'],['draft'],{'status':'submitted'})
    event(row,'submitted',{'version':row.version})
    db.session.commit()
    return jsonify(view(row))


@material_bp.post('/<category>/records/<int:record_id>/check')
def check_record(category,record_id):
    row=record_at(category,record_id)
    payload=body(); object_keys(payload,{'version'},{'version'})
    report=check(row)
    version_change(row,payload['version'],['draft','submitted','needs_correction'],{'check_report':report})
    event(row,'data_checked',{'version':row.version,'report':report})
    db.session.commit()
    return jsonify(view(row))


@material_bp.post('/<category>/records/<int:record_id>/review')
def review(category,record_id):
    row=record_at(category,record_id)
    authorize(row,staff=True)
    payload=body(); object_keys(payload,{'version','decision','comment'},{'version','decision','comment'})
    if payload['decision'] not in ('verified','rejected','needs_correction'):
        raise ValueError('decision必须为verified/rejected/needs_correction')
    comment=text(payload['comment'],'核验说明',maximum=2000)
    version_change(row,payload['version'],['submitted'],{'status':payload['decision']})
    event(row,'reviewed',{'version':row.version,'decision':row.status,'comment':comment,
                         'data_snapshot':row.data,'check_report_snapshot':row.check_report,
                         'attachments_snapshot':[{'id':f.id,'filename':f.filename,'size':f.size,'sha256':f.sha256}
                                                 for f in row.attachments]})
    db.session.commit()
    return jsonify(view(row))


@material_bp.get('/<category>/records/<int:record_id>/events')
def events(category,record_id):
    row=record_at(category,record_id)
    return jsonify({'events':[{'id':e.id,'actor_id':e.actor_id,'action':e.action,'details':e.details,'created_at':e.created_at.isoformat()+'Z'} for e in row.events]})


@material_bp.post('/<category>/records/<int:record_id>/withdraw')
def withdraw(category,record_id):
    row=record_at(category,record_id)
    if actor().role!='student':
        abort(403,description='仅学生本人可撤回未核验材料')
    payload=body(); object_keys(payload,{'version'},{'version'})
    version_change(row,payload['version'],['submitted'],{'status':'draft','check_report':None})
    event(row,'withdrawn',{'version':row.version})
    db.session.commit()
    return jsonify(view(row))


@material_bp.post('/<category>/records/<int:record_id>/attachments')
def upload(category,record_id):
    row=record_at(category,record_id)
    if actor().role!='student':
        abort(403,description='仅学生本人可上传附件')
    version=integer(int(request.form.get('version','0')),'version',1,2_000_000_000)
    files=request.files.getlist('files')
    if not 1<=len(files)<=10 or len(row.attachments)+len(files)>10:
        raise ValueError('每条材料最多10个附件')
    limit=current_app.config.get('MATERIAL_MAX_FILE_BYTES',10*1024*1024)
    prepared=[]
    for f in files:
        name=Path((f.filename or '').replace('\\','/')).name
        if not name or len(name)>255 or any(ord(c)<32 or ord(c)==127 or 0xD800<=ord(c)<=0xDFFF for c in name) or Path(name).suffix.lower() not in ('.pdf','.jpg','.jpeg','.png','.webp','.csv','.xlsx'):
            raise ValueError('附件仅支持PDF、图片、CSV、XLSX')
        payload=f.stream.read(limit+1)
        if not payload or len(payload)>limit:
            raise ValueError('每个附件必须为非空且不超过10MB')
        prepared.append((name,payload))
    # 先CAS取得本版本的修改权，再写私有文件；失败仅删除本请求新建的文件。
    version_change(row,version,['draft','needs_correction'],{'status':'draft','check_report':None})
    created=[]
    try:
        for name,payload in prepared:
            stored=uuid.uuid4().hex+Path(name).suffix.lower()
            path=stored_path(stored); path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as output:
                created.append(path)
                output.write(payload)
            db.session.add(MaterialAttachment(record_id=row.id,filename=name,stored_name=stored,
                                               sha256=hashlib.sha256(payload).hexdigest(),size=len(payload)))
        event(row,'attachments_added',{'version':row.version,'filenames':[n for n,_ in prepared]})
        db.session.commit()
    except Exception:
        db.session.rollback()
        for path in created:
            path.unlink(missing_ok=True)
        raise
    db.session.expire(row,['attachments'])
    return jsonify(view(row)),201


@material_bp.get('/<category>/records/<int:record_id>/attachments/<int:attachment_id>')
def download(category,record_id,attachment_id):
    row=record_at(category,record_id)
    attachment=db.get_or_404(MaterialAttachment,attachment_id)
    if attachment.record_id!=row.id:
        abort(404)
    path=stored_path(attachment.stored_name)
    if not path.is_file():
        abort(404)
    if path.stat().st_size != attachment.size:
        abort(409, description='原件大小与上传记录不一致，已停止下载，请核对原件')
    digest = hashlib.sha256()
    with path.open('rb') as original:
        for block in iter(lambda: original.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != attachment.sha256:
        abort(409, description='原件校验失败，文件可能被修改，已停止下载')
    response=send_file(path,as_attachment=True,download_name=attachment.filename)
    response.headers['Cache-Control']='private, no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response


@material_bp.post('/sources/import')
def source_import():
    result=import_sources(body())
    db.session.commit()
    return jsonify(result),201 if result['created_count'] else 200


@material_bp.get('/sources/<int:source_id>')
def source_detail(source_id):
    row=db.get_or_404(MaterialSource,source_id)
    authorize(row,staff=True)
    return jsonify({'id':row.id,'category':row.category,'student_id':row.student_id,'year':row.year,
                    'external_id':row.external_id,'revision':row.revision,'source_name':row.source_name,
                    'source_url':row.source_url,'data':row.data,'digest':row.digest,
                    'imported_by':row.imported_by,'created_at':row.created_at.isoformat()+'Z'})


@material_bp.post('/academic/parse-csv')
def parse_csv():
    actor()
    file=request.files.get('file')
    if not file:
        raise ValueError('请上传file字段的UTF-8 CSV文件')
    payload=file.stream.read(2*1024*1024+1)
    if len(payload)>2*1024*1024:
        raise ValueError('成绩CSV不能超过2MB')
    try:
        content = payload.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise ValueError('CSV必须采用UTF-8编码') from None
    columns=['course_code','course_name','credits','score','full_score']
    rows=[]
    try:
        reader=csv.DictReader(io.StringIO(content,newline=''), strict=True)
        headers=reader.fieldnames
        if not headers or len(headers)!=len(set(headers)) or set(headers)!=set(columns):
            raise ValueError('CSV列必须为：'+','.join(columns))
        for row in reader:
            if len(rows)>=1000 or None in row or any(v is None for v in row.values()):
                raise ValueError('CSV行数或列数无效')
            rows.append(row)
    except csv.Error:
        raise ValueError('CSV内容格式无效') from None
    normalized=normalize('academic',{'term':text(request.form.get('term',''),'学期'),'courses':rows})
    return jsonify({'data':normalized,'analysis':analyze('academic',normalized),
                    'persisted':False,'note':'仅解析预览；学生自行提交或管理员核验来源后导入。'})


@material_bp.post('/<category>/records/<int:record_id>/recognize')
def recognize(category,record_id):
    record_at(category,record_id)
    return jsonify({'error':'该类别的新OCR识别适配器尚未实现','code':'recognition_not_implemented',
                    'ocr_executed':False,'category':category,'record_id':record_id,
                    'next_step':'人工核验或上传结构化数据；已有蓝桥杯功能使用/api/certificates'}),501


@material_bp.get('/openapi.json')
def openapi():
    actor()
    path = Path(__file__).resolve().parents[1] / 'docs' / 'openapi-materials.json'
    return send_file(path, mimetype='application/json')
