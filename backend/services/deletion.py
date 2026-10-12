"""旧管理删除入口的材料保护：数据库成功提交后才清理普通申请附件。"""
import os
from pathlib import Path
from flask import current_app, jsonify
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from extensions import db
from models import Student
from automation_models import AutomationBatch, AutomationFingerprint, AutomationPolicy, AutomationReview


def automation_deletion_conflict(students=(), users=(), *, faculty_id=None, applications=()):
    student_ids = sorted({student.student_id for student in students})
    # 与识别、提交和审核一致的学生锁顺序。并发外键冲突仍由提交失败兜底。
    if student_ids:
        Student.query.filter(Student.student_id.in_(student_ids)).order_by(
            Student.student_id).with_for_update().all()
    conditions = []
    if student_ids:
        conditions.append(AutomationBatch.student_id.in_(student_ids))
    application_ids = [application.id for application in applications]
    if application_ids:
        conditions.append(AutomationBatch.application_id.in_(application_ids))
    if faculty_id is not None:
        conditions.append(AutomationBatch.faculty_id == faculty_id)
        if AutomationPolicy.query.filter_by(faculty_id=faculty_id).first():
            return "该学院已有自动化审核政策，不能直接删除学院"
    if conditions and AutomationBatch.query.filter(or_(*conditions)).first():
        return "存在自动化材料或加分记录，不能直接删除；请保留记录并停用相关账号"
    if student_ids and AutomationFingerprint.query.filter(
            AutomationFingerprint.student_id.in_(student_ids)).first():
        return "存在自动化材料去重记录，不能直接删除；请停用相关账号"
    user_ids = [user.id for user in users]
    if user_ids and AutomationReview.query.filter(AutomationReview.reviewer_id.in_(user_ids)).first():
        return "账号关联自动化审核审计记录，不能直接删除；请停用账号"
    return None


def protected_deletion_response(message):
    db.session.rollback()
    return jsonify({"message": message}), 409


def commit_deletion(applications):
    """只清理 FILE_FOLDER 内附件，回滚、外键冲突均不得触碰文件。"""
    root = Path(current_app.config.get("FILE_FOLDER", "")).resolve()
    paths = set()
    for application in applications:
        for attachment in application.files or []:
            if not isinstance(attachment, dict) or not isinstance(attachment.get("path"), str):
                continue
            path = root / os.path.basename(attachment["path"])
            # 拒绝目录本身、越界和指向其他目录的符号链接。
            if current_app.config.get("FILE_FOLDER") and path.resolve().parent == root:
                paths.add(path)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"message": "存在关联记录，无法删除；附件已保留"}), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception("删除数据库记录失败，附件已保留")
        return jsonify({"message": "删除失败，记录及附件已保留"}), 500
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # DB 已提交，不应再尝试回滚；保留未清理文件并记日志供运维处理。
            current_app.logger.exception("数据库删除成功，但附件未清理：%s", path)
    return None
