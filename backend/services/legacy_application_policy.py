"""One access boundary for compatibility application writes; never owns a transaction."""
from flask import abort
from domain.review_stages import REVIEW_ROLES
from models import Student
from services.actors import actor

IDENTITY_FIELDS = ("student_id", "student_name", "faculty_id", "department_id", "major_id")
REVIEW_FIELDS = {"review_stage", "review_version", "review_history", "final_score", "review_comment", "reviewed_at", "reviewed_by", "applied_at", "created_at", "updated_at"}
EDITABLE = {"draft", "pending", "needs_correction"}


def application_actor():
    return actor()


def bind_student_identity(data, user):
    if user.role != "student" or not user.student_id:
        abort(403, description="仅学生本人可创建旧申请")
    if not isinstance(data, dict):
        abort(400, description="申请内容必须是对象")
    owner = Student.query.filter_by(student_id=user.student_id).one_or_none()
    if owner is None or not user.faculty_id or owner.faculty_id != user.faculty_id:
        abort(403, description="学生账号与学院关联不完整，请联系管理员")
    for field in IDENTITY_FIELDS:
        value = getattr(owner, field)
        if field in data and str(data[field]) != str(value):
            abort(403, description="不能修改所属学生、学院、系或专业信息")
        data[field] = value
    if data.get("status", "pending") not in {"draft", "pending"}:
        abort(409, description="学生只能创建草稿或待审核申请")
    if REVIEW_FIELDS.intersection(data):
        abort(409, description="审核结果与系统时间不能通过申请填写接口修改")


def authorize_write(application, user, *, action):
    if action == "review":
        if user.role not in REVIEW_ROLES or not user.faculty_id or user.faculty_id != application.faculty_id:
            abort(403, description="只能审核本学院申请")
        return
    if user.role != "student" or user.student_id != application.student_id or user.faculty_id != application.faculty_id:
        abort(403, description="仅学生本人可以修改或删除自己的申请")
    if action == "edit" and application.status not in EDITABLE:
        abort(409, description="已处理申请只读，不能直接修改历史结果")


def validate_edit(data, application):
    if not isinstance(data, dict):
        abort(400, description="申请内容必须是对象")
    if REVIEW_FIELDS.intersection(data):
        # 与创建路径保持一致：篡改审核结果属于状态冲突，用 409 而不是 400
        abort(409, description="学生不能修改审核结果或系统时间")
    for field in IDENTITY_FIELDS:
        if field in data and str(data[field]) != str(getattr(application, field)):
            # 与 bind_student_identity 的 403 对齐：这是越权，不是格式错误
            abort(403, description="申请不能更改所属学生或学院")
    if data.get("status", application.status) not in {"draft", "pending"}:
        abort(409, description="状态只能通过相应提交、撤回或审核入口修改")
    if "files" in data:
        files = data["files"]
        allowed = {item.get("path") for item in application.files or []}
        if not isinstance(files, list) or any(not isinstance(item, dict) or item.get("path") not in allowed for item in files):
            abort(400, description="不能引用其他申请的附件")


def protect_deletion(application):
    from automation_models import AutomationBatch
    from certificate_models import CertificateAssessment
    from material_models import MaterialRecord
    from workflow_models import ScoreEntry, ReviewScoringCommand
    protected = (
        CertificateAssessment.query.filter_by(application_id=application.id).first() or
        MaterialRecord.query.filter_by(application_id=application.id).first() or
        AutomationBatch.query.filter_by(application_id=application.id).first() or
        ScoreEntry.query.filter(ScoreEntry.source_id == str(application.id),
            ScoreEntry.source_type.in_(["legacy_application", "certificate", "volunteer_automation"])).first() or
        ReviewScoringCommand.query.filter(ReviewScoringCommand.source_id == str(application.id),
            ReviewScoringCommand.source_type.in_(["legacy_application", "certificate", "volunteer_automation"])).first()
    )
    if protected or application.review_history:
        abort(409, description="申请关联识别、材料、计分或审核证据，不能直接删除")
    if application.status != "draft":
        abort(409, description="只能删除未关联证据的草稿；已提交或已处理申请须保留历史")
