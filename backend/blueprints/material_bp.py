"""结构化材料、独立OCR与统一审核计分入口。"""
import csv
import hashlib
import io
import json
from pathlib import Path
import uuid
from domain.student_work_scoring import POLICY_VERSION as WORK_POLICY
from flask import Blueprint, abort, current_app, jsonify, request, send_file
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException
from extensions import db
from material_models import CompetitionOcrJob, MaterialRecord, MaterialAttachment, MaterialSource
from services.automation import actor
from services.materials.schemas import (RESEARCH_TYPES, TYPES, type_view, normalize, analyze, integer, text, object_keys)
from services.materials.service import (body, record_at, category_exists, authorize, view,
                                       version_change, event, stored_path, check, import_sources)
from use_cases.materials import (
    MaterialUseCaseError,
    add_attachments,
    abandon_returned_competition,
    create_material,
    competition_review_context,
    competition_workflow_context,
    competition_workbench_summary,
    confirm_available_rule,
    create_correction_version,
    edit_material,
    review_material,
    reconfirm_competition_rule,
    student_noncompetition_summary,
    teacher_noncompetition_summary,
    submit_material,
    validate_competition_review_command,
    withdraw_material,
)
from workflow_models import CompetitionRulePackage, MaterialReviewCommand
from use_cases.competition_review import review_competition_material, student_competition_feedback, teacher_competition_summary
from use_cases.competition_ocr import start_competition_ocr, cancel_competition_ocr
from use_cases.manual_materials import is_manual, submit_manual, review_manual
from use_cases.scoring import ScoringUseCaseError

material_bp=Blueprint('materials',__name__,url_prefix='/api/materials')


@material_bp.errorhandler(HTTPException)
def http_error(error):
    db.session.rollback()
    return jsonify({'error':error.description}),error.code


@material_bp.errorhandler(ValueError)
def invalid(error):
    db.session.rollback()
    return jsonify({'error':str(error)}),400


@material_bp.errorhandler(MaterialUseCaseError)
@material_bp.errorhandler(ScoringUseCaseError)
def use_case_error(error):
    db.session.rollback()
    return jsonify({'error':str(error),'code':error.code}),error.status_code


@material_bp.errorhandler(IntegrityError)
def conflict(error):
    db.session.rollback()
    message = str(getattr(error, 'orig', error))
    if ('ix_material_competition_duplicate' in message or
            'material_record.student_id, material_record.year, material_record.competition_duplicate_digest' in message):
        return jsonify({'error':'相同竞赛材料已经提交','code':'duplicate_submission'}),409
    return jsonify({'error':'记录发生并发冲突，整批未保存，请刷新重试'}),409


@material_bp.get('/types')
def types():
    actor()
    return jsonify(type_view())


def _competition_package_for_reader():
    package, _context = competition_workflow_context(actor())
    return package


@material_bp.get('/competition/context')
def competition_context():
    package, context = competition_workflow_context(
        actor(), expected_digest=request.headers.get('If-Match')
    )
    response = jsonify(context)
    response.headers['ETag'] = f'"{package.digest}"'
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@material_bp.get('/competition/rules/current')
def competition_current_package():
    package, context = competition_workflow_context(actor())
    return jsonify({
        'package_id': package.package_id,
        'version': package.version,
        'digest': package.digest,
        'cycle_code': context['cycle']['cycle_code'],
        'evidence_period': context['evidence_period'],
        'catalog_count': context['catalog']['count'],
        'field_schema': context['field_schema'],
        'allowed_actions': context['allowed_actions'],
    })


@material_bp.post('/competition/estimate')
def estimate_competition_route():
    from domain.competition_rules import normalize_competition_facts, CompetitionPackageError
    user=actor()
    if user.role!='student': abort(403)
    package,_=competition_workflow_context(user)
    payload=body();object_keys(payload,{'data'},{'data'})
    try:
        facts=normalize_competition_facts(package.snapshot,payload['data'])
    except CompetitionPackageError as error:
        raise MaterialUseCaseError(str(error),code=error.code) from error
    return jsonify({'declared_estimate':facts['candidate_score'], 'ocr_suggested_score':None,
                    'requires_teacher_review':True, 'rule_package_id':package.id,
                    'notice':'按手填信息计算单项候选分；最终计入分受审核、去重与上限影响。'})


@material_bp.get('/competition/workbench-summary')
def competition_workbench():
    return jsonify(competition_workbench_summary(actor()))


@material_bp.get('/student/summary')
def student_summary():
    return jsonify(student_noncompetition_summary(actor()))


@material_bp.get('/teacher/summary')
def teacher_summary():
    return jsonify(teacher_noncompetition_summary(actor()))


@material_bp.get('/competition/catalog')
def competition_catalog():
    package = _competition_package_for_reader()
    query = (request.args.get('q') or '').strip().casefold()
    catalog = package.snapshot['catalog']
    if query:
        catalog = [item for item in catalog if query in item['name'].casefold()]
    return jsonify({'package_id': package.package_id, 'digest': package.digest, 'items': [
        {
            'competition_id': item['competition_id'], 'name': item['name'],
            'category': item['category'], 'levels': item['levels'],
            'event_family': item['event_family'],
        }
        for item in catalog
    ]})


@material_bp.get('/competition/catalog/<competition_id>')
def competition_catalog_item(competition_id):
    package = _competition_package_for_reader()
    item = next((value for value in package.snapshot['catalog']
                 if value['competition_id'] == competition_id), None)
    if item is None:
        return jsonify({'error': '竞赛不在当前正式目录', 'code': 'unknown_competition'}), 404
    schema = package.snapshot['field_schema']
    levels = item['levels']
    return jsonify({
        'package_id': package.package_id,
        'competition': {
            'competition_id': item['competition_id'], 'name': item['name'],
            'category': item['category'], 'organizer': item['organizer'],
            'event_family': item['event_family'],
        },
        'field_schema': {
            'required': schema['required'],
            'participation_modes': schema['participation_modes'],
            'team_required': schema['team_required'],
            'levels': levels,
            'awards_by_level': {level: schema['awards'][level] for level in levels},
            'formats': item.get('formats', []),
        },
    })


def create_manual_with_files(category,user):
    from services.materials.ocr_schemas import MANUAL_TYPES
    from services.materials.attachments import prepare_uploads
    if category not in MANUAL_TYPES | RESEARCH_TYPES | {'innovation_training', 'student_work','competition','volunteer'}:
        raise ValueError('该类别请使用正式材料申报接口')
    object_keys(request.form,{'year','data'},{'year','data'})
    try:
        payload=json.loads(request.form['data'])
    except (ValueError,TypeError):
        raise ValueError('人工材料字段必须为JSON对象') from None
    files=prepare_uploads(request.files.getlist('files'),current_app.config.get('MATERIAL_MAX_FILE_BYTES',10*1024*1024))
    created=[]
    job=None
    volunteer_dirs=[]
    try:
        row=create_material(user,category,{'year':integer(int(request.form['year']),'year',2000,2100),
                                         'data':payload,**({'manual_only':True} if category not in RESEARCH_TYPES | {'innovation_training', 'competition','volunteer'} else {})})
        row,created=add_attachments(user,row,row.version,files,stored_path('placeholder').parent)
        if category=='competition':
            from services.competition_ocr.bridge import enqueue_created_material
            job=enqueue_created_material(user,row)
        elif category=='volunteer':
            from services.volunteer_ocr import queue
            queue(row,user,volunteer_dirs)
        db.session.commit()
    except Exception:
        db.session.rollback()
        for path in created:
            path.unlink(missing_ok=True)
        for folder in volunteer_dirs:
            import shutil
            shutil.rmtree(folder,ignore_errors=True)
        if job is not None:
            import shutil
            from services.competition_ocr.jobs import job_root
            shutil.rmtree(job_root(job.job_id),ignore_errors=True)
        raise
    return jsonify(view(row)),201


def update_competition_with_files(user,row):
    from services.materials.attachments import prepare_uploads
    from services.competition_ocr.bridge import enqueue_created_material
    object_keys(request.form,{'version','data'},{'version','data'})
    data=json.loads(request.form['data'])
    version=integer(int(request.form['version']),'version',1,2_000_000_000)
    incoming=request.files.getlist('files')
    files=prepare_uploads(incoming,current_app.config.get('MATERIAL_MAX_FILE_BYTES',10*1024*1024),len(row.attachments)) if incoming else []
    created=[]
    job=None
    try:
        edit_material(user,row,version,data)
        if files:
            row,created=add_attachments(user,row,row.version,files,stored_path('placeholder').parent)
        job=enqueue_created_material(user,row)
        db.session.commit()
    except Exception:
        db.session.rollback()
        for path in created: path.unlink(missing_ok=True)
        if job is not None:
            import shutil
            from services.competition_ocr.jobs import job_root
            shutil.rmtree(job_root(job.job_id),ignore_errors=True)
        raise
    return jsonify(view(row))


@material_bp.route('/<category>/records',methods=['GET','POST'])
def records(category):
    category_exists(category)
    user=actor()
    if request.method=='POST':
        if request.mimetype == 'multipart/form-data':
            return create_manual_with_files(category,user)
        row=create_material(user,category,body())
        db.session.commit()
        return jsonify(view(row)),201
    query=MaterialRecord.query.filter_by(category=category)
    if user.role=='student':
        query=query.filter_by(student_id=user.student_id)
    elif user.role=='teacher' and user.faculty_id:
        from services.materials.ocr_schemas import MANUAL_TYPES
        # 已审核态必须包含竞赛：竞赛材料审核后是 needs_correction/scored，
        # 旧写法只放行人工材料类别，导致教师永远查不到竞赛审核记录。
        reviewed_categories = MANUAL_TYPES | RESEARCH_TYPES | {
            'innovation_training', 'student_work', 'volunteer', 'competition',
        }
        statuses = ('verified','rejected','needs_correction','scored','verified_not_eligible') if request.args.get('reviewed') == '1' and category in reviewed_categories else ('submitted','under_review')
        query=query.filter_by(faculty_id=user.faculty_id).filter(MaterialRecord.status.in_(statuses))
        from services.materials.ocr_schemas import MANUAL_TYPES
        if category == 'student_work':
            query = query.filter(or_(MaterialRecord.rule_version_id.isnot(None), MaterialRecord.ocr_raw_terms.isnot(None), MaterialRecord.analysis["manual_only"].as_boolean().is_(True)))
        elif category != 'competition' and category not in MANUAL_TYPES:
            query = query.filter(MaterialRecord.rule_version_id.isnot(None))
        elif category == 'competition':
            query = query.filter(or_(
                MaterialRecord.competition_rule_package_id.isnot(None),
                MaterialRecord.rule_version_id.isnot(None),
            ))
    elif user.role=='admin' and user.faculty_id:
        query=query.filter_by(faculty_id=user.faculty_id)
    else:
        abort(403)
    for name in ('student_id','status'):
        if request.args.get(name):
            query=query.filter(getattr(MaterialRecord,name)==request.args[name])
    if user.role == 'student' and not request.args.get('status'):
        query = query.filter(MaterialRecord.status != 'abandoned')
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
    if request.mimetype=='multipart/form-data':
        if category!='competition': raise ValueError('该保存方式仅用于竞赛材料')
        return update_competition_with_files(user,row)
    payload=body()
    object_keys(payload,{'version','data'},{'version','data'})
    edit_material(user,row,payload['version'],payload['data'])
    db.session.commit()
    return jsonify(view(row))


@material_bp.post('/<category>/records/<int:record_id>/submit')
def submit(category,record_id):
    row=record_at(category,record_id)
    user=actor()
    payload=body(); object_keys(payload,{'version'},{'version'})
    if category == 'volunteer':
        from use_cases.volunteer_materials import submit_volunteer
        submit_volunteer(user,row,payload['version'])
    elif row.normalization_version == WORK_POLICY:
        submit_material(user,row,payload["version"])
    elif is_manual(row):
        submit_manual(user,row,payload['version'])
    else:
        submit_material(user,row,payload['version'])
    db.session.commit()
    return jsonify(view(row))


@material_bp.post('/volunteer/records/<int:record_id>/ocr')
def volunteer_ocr_start(record_id):
    from services.volunteer_ocr import queue
    from use_cases.materials import _authorize_transition, _cas_change
    row=record_at('volunteer',record_id)
    user=actor(); payload=body()
    object_keys(payload,{'version'},{'version'})
    _authorize_transition(user,row,'edit','draft')
    folders=[]
    try:
        _cas_change(row,payload['version'],('draft','needs_correction'),{'status':'draft'})
        queue(row,user,folders)
        db.session.commit()
    except Exception:
        db.session.rollback()
        import shutil
        for folder in folders: shutil.rmtree(folder,ignore_errors=True)
        raise
    return jsonify(view(row)),202


@material_bp.post('/volunteer/records/<int:record_id>/appeal')
def volunteer_appeal(record_id):
    from use_cases.volunteer_materials import appeal_volunteer
    row=record_at('volunteer',record_id)
    payload=body(); object_keys(payload,{'version','reason'},{'version','reason'})
    appeal_volunteer(actor(),row,payload['version'],payload['reason'])
    db.session.commit()
    return jsonify(view(row))


@material_bp.post('/<category>/records/<int:record_id>/reconfirm-submit')
def reconfirm_submit(category, record_id):
    row = record_at(category, record_id)
    user = actor()
    payload = body()
    if category == 'competition':
        object_keys(payload, {'version', 'confirmed_terms', 'confirmed'},
                    {'version', 'confirmed_terms', 'confirmed'})
        replacement = reconfirm_competition_rule(
            user, row, payload['version'], payload['confirmed_terms'], payload['confirmed']
        )
        db.session.commit()
        return jsonify(view(replacement)), 201
    object_keys(payload, {'version', 'rule_version_id', 'confirmed'},
                {'version', 'rule_version_id', 'confirmed'})
    row, rule = confirm_available_rule(
        user, row, payload['version'], payload['rule_version_id'], payload['confirmed']
    )
    db.session.commit()
    result = view(row); result['rule_match'] = rule
    return jsonify(result)


@material_bp.post('/<category>/records/<int:record_id>/corrections')
def create_correction(category, record_id):
    row = record_at(category, record_id)
    user = actor(); payload = body()
    object_keys(payload, {'version', 'confirmed_terms'}, {'version', 'confirmed_terms'})
    corrected = create_correction_version(
        user, row, payload['version'], payload['confirmed_terms']
    )
    db.session.commit()
    result = view(corrected)
    result.update({"supersedes_record_id": row.id,
                   "correction_sequence": corrected.correction_sequence,
                   "evidence_source_record_id": row.id})
    return jsonify(result), 201


@material_bp.post('/<category>/records/<int:record_id>/abandon')
def abandon_correction(category, record_id):
    row = record_at(category, record_id)
    user = actor(); payload = body()
    object_keys(payload, {'version'}, {'version'})
    if category == 'competition':
        abandon_returned_competition(user, row, payload['version'])
    else:
        from use_cases.materials import transition_material
        transition_material(user, row, payload['version'], 'abandon', 'abandoned')
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
    row=record_at(category,record_id,allow_teacher_processed=True)
    user=actor()
    payload=body()
    if category == "student_work" and row.normalization_version == WORK_POLICY:
        from domain.student_work_scoring import candidate
        from services.materials.schemas import normalize_student_work
        from use_cases.research_review import review_policy_material
        result, replayed = review_policy_material(user, row, payload, WORK_POLICY, normalize_student_work, candidate, None)
        db.session.commit()
        return jsonify({**result, "replayed": replayed})
    if category == "innovation_training":
        from domain.innovation_scoring import POLICY_VERSION, candidate
        from services.materials.schemas import normalize_innovation
        from use_cases.research_review import review_policy_material
        result, replayed = review_policy_material(user, row, payload, POLICY_VERSION,
                                                  normalize_innovation, candidate, "project_key")
        db.session.commit()
        return jsonify({**result, "replayed": replayed})
    if category in RESEARCH_TYPES:
        from use_cases.research_review import review_research
        result, replayed = review_research(user, row, payload)
        db.session.commit()
        return jsonify({**result, "replayed": replayed})
    if is_manual(row):
        object_keys(payload, {'version','decision','comment'}, {'version','decision'})
        review_manual(user,row,payload)
        db.session.commit()
        return jsonify(view(row))
    if category == 'competition':
        # Validate the dedicated command before the atomic executor (task 4.3)
        # sees any request.  Legacy decision names and override fields are
        # deliberately unavailable on this route.
        result, replayed = review_competition_material(user, row, payload)
        db.session.commit()
        result['replayed'] = replayed
        return jsonify(result)
    object_keys(payload,{'version','decision','comment','idempotency_key','override_score','override_reason'},
                {'version','decision','comment'})
    key=payload.get('idempotency_key') or f"legacy:{user.id}:{row.id}:{payload['version']}:{payload['decision']}"
    _,replayed=review_material(user,row,payload['version'],payload['decision'],payload['comment'],key,
                               payload.get('override_score'),payload.get('override_reason'))
    db.session.commit()
    command=MaterialReviewCommand.query.filter_by(record_id=row.id,idempotency_key=key).one()
    result=view(row); result.update(command.result['scoring']); result['replayed']=replayed
    if result['scoring_status']=='needs_rule':
        result['code']='needs_rule'
    return jsonify(result),200 if result['overall_status']=='complete' else 409


@material_bp.get('/competition/records/<int:record_id>/review-context')
def competition_review_context_route(record_id):
    row = record_at('competition', record_id, allow_teacher_processed=True)
    return jsonify(competition_review_context(actor(), row))


@material_bp.get('/competition/students/<student_id>/summary')
def competition_student_summary_route(student_id):
    year = integer(int(request.args.get('year', '2028')), 'year', 2000, 2100)
    return jsonify(teacher_competition_summary(actor(), student_id, year))


@material_bp.get('/competition/feedback')
def competition_feedback_route():
    year = integer(int(request.args.get('year', '2028')), 'year', 2000, 2100)
    return jsonify(student_competition_feedback(actor(), year))


@material_bp.post('/competition/records/<int:record_id>/ocr')
def competition_ocr_start_route(record_id):
    row = record_at('competition', record_id); payload = body()
    object_keys(payload, {'version'}, {'version'})
    from services.competition_ocr.bridge import queue_material
    job, created = queue_material(row, payload['version'])
    return jsonify({'job_id': job.job_id, 'status': job.status,
                    'material_version': job.material_version}), 201 if created else 200


@material_bp.get('/competition/records/<int:record_id>/ocr/<job_id>')
def competition_ocr_status_route(record_id, job_id):
    row = record_at('competition', record_id); user = actor()
    if user.role != 'student' or user.student_id != row.student_id: abort(403)
    job = CompetitionOcrJob.query.filter_by(record_id=row.id, job_id=job_id).one_or_none()
    if job is None: abort(404)
    return jsonify({'job_id': job.job_id, 'status': job.status,
        'material_version': job.material_version, 'raw_result': job.raw_result,
        'error': job.error, 'late_result_ignored': job.ignored_late_result is not None})


@material_bp.post('/competition/records/<int:record_id>/ocr/<job_id>/cancel')
def competition_ocr_cancel_route(record_id, job_id):
    row = record_at('competition', record_id); payload = body()
    object_keys(payload, {'version'}, {'version'})
    job = cancel_competition_ocr(actor(), row, payload['version'], job_id)
    db.session.commit()
    return jsonify({'job_id': job.job_id, 'status': job.status, 'version': row.version})


@material_bp.get('/<category>/records/<int:record_id>/events')
def events(category,record_id):
    row=record_at(category,record_id)
    return jsonify({'events':[{'id':e.id,'actor_id':e.actor_id,'action':e.action,'details':e.details,'created_at':e.created_at.isoformat()+'Z'} for e in row.events]})


@material_bp.post('/<category>/records/<int:record_id>/withdraw')
def withdraw(category,record_id):
    row=record_at(category,record_id)
    user=actor()
    payload=body(); object_keys(payload,{'version'},{'version'})
    withdraw_material(user,row,payload['version'])
    db.session.commit()
    return jsonify(view(row))


@material_bp.post('/<category>/records/<int:record_id>/attachments')
def upload(category,record_id):
    row=record_at(category,record_id)
    user=actor()
    version=integer(int(request.form.get('version','0')),'version',1,2_000_000_000)
    from services.materials.attachments import prepare_uploads
    prepared_files=prepare_uploads(request.files.getlist('files'),
        current_app.config.get('MATERIAL_MAX_FILE_BYTES',10*1024*1024),len(row.attachments))
    created=[]
    try:
        row,created=add_attachments(user,row,version,prepared_files,stored_path('placeholder').parent)
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
    row=record_at(category,record_id, allow_teacher_processed=(category == 'competition'))
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
    response=send_file(
        path, as_attachment=request.args.get('inline') != '1',
        download_name=attachment.filename,
    )
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
    payload=request.get_json(silent=True)
    from services.materials.schemas import OCR_CATEGORIES
    if payload is not None and category in OCR_CATEGORIES:
        from services.materials.recognition import recognize_attachment
        from services.competition_ocr.jobs import job_view
        return jsonify(job_view(recognize_attachment(category,record_id,payload))),202
    return jsonify({'error':'该类别尚未适配或未提供附件识别参数' ,'code':'recognition_not_implemented',
                    'ocr_executed':False,'category':category,'record_id':record_id,
                    'next_step':'人工核验或上传结构化数据；已有蓝桥杯功能使用/api/certificates'}),501


@material_bp.get('/openapi.json')
def openapi():
    actor()
    path = Path(__file__).resolve().parents[1] / 'docs' / 'openapi-materials.json'
    return send_file(path, mimetype='application/json')
