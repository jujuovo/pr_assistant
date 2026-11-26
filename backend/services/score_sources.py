"""Read-only project detail, bounded by the student's authorized score explanation."""
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import quote
from material_models import MaterialRecord
from services.materials.service import record_at, view
from use_cases.scoring import ScoringUseCaseError, explain_student_score


def _legacy_time(value):
    return (value if value.tzinfo else value.replace(tzinfo=ZoneInfo("Asia/Shanghai"))).isoformat() if value else None


def _files(files):
    result=[]
    for index,file in enumerate(files or []):
        file=file if isinstance(file,dict) else {'path':file}
        raw=file.get('url') or file.get('path') or ''
        if not isinstance(raw,str):continue
        path=raw.replace(chr(92),'/')
        if path.startswith('uploads/'):path='/'+path
        if Path(raw).is_absolute() and not path.startswith(('/uploads/','/api/')):
            path='/uploads/files/'+quote(path.rsplit('/',1)[-1])
        if not path.startswith(('/uploads/','/api/')):continue
        result.append({'id':index,'filename':file.get('name') or file.get('filename') or path.rsplit('/',1)[-1], 'url':path})
    return result


def score_source_detail(user, student, year, source_type, source_id):
    if not ((user.role=='student' and user.student_id==student.student_id) or
            (user.role in {'teacher','admin'} and user.faculty_id and user.faculty_id==student.faculty_id)):
        raise ScoringUseCaseError('没有该学生的材料详情权限',status_code=403,code='forbidden')
    sources=explain_student_score(student.student_id,year)['entries']
    matched=next((entry for entry in sources if entry['project_source']['type']==source_type
                  and entry['project_source']['id']==str(source_id)),None)
    if matched is None:
        raise ScoringUseCaseError('该计分项目不存在或不属于当前学生及周期',code='score_source_not_found')
    if source_type=='material':
        row=MaterialRecord.query.filter_by(id=source_id,student_id=student.student_id,faculty_id=student.faculty_id).one_or_none()
        if row is None:raise ScoringUseCaseError('原材料记录不存在',code='score_source_not_found')
        record_at(row.category,row.id,allow_teacher_processed=True)
        material=view(row)
        history=[{'id':event.id,'action':event.action,'comment':(event.details or {}).get('comment'),
                  'created_at':event.created_at.isoformat()+'Z'} for event in sorted(row.events,key=lambda e:(e.created_at,e.id))]
        return {'title':matched['project_source'].get('name') or '项目材料', 'status':row.status,
                'data':row.data,'attachments':material['attachments'],'ocr_raw_terms':row.ocr_raw_terms,
                'history':history,'updated_at':material['updated_at']}
    if source_type in {'legacy_application','volunteer_automation'} and 'application' in MaterialRecord.metadata.tables:
        from legacy_models import Application
        row=Application.query.filter_by(id=source_id,student_id=student.student_id,faculty_id=student.faculty_id).one_or_none()
        if row is None:raise ScoringUseCaseError('原申请记录不存在',code='score_source_not_found')
        data={'project_name':row.project_name,'award_date':row.award_date.isoformat() if row.award_date else None,
              'description':row.description}
        history=[{'id':row.id,'action':'approved' if row.status=='approved' else row.status,
                  'comment':row.review_comment,'created_at':_legacy_time(row.reviewed_at)}] if row.reviewed_at else []
        return {'title':row.project_name,'status':row.status,'data':data,'attachments':_files(row.files),
                'ocr_raw_terms':None,'history':history,'updated_at':_legacy_time(row.reviewed_at) if row.reviewed_at else None}
    raise ScoringUseCaseError('该来源暂不提供详情',code='score_source_not_supported')
