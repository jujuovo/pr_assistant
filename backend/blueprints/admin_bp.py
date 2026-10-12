# -*- coding: utf-8 -*-
"""
管理员管理蓝图

该文件负责处理管理员相关的API端点，包括：
- 学院管理（增删改查）
- 系管理（增删改查）
- 专业管理（增删改查）
- 系统设置管理（获取、更新）
- 推免相关文件管理（上传、下载、删除）
"""

import os
import uuid
from flask import (
    Blueprint,
    request,
    jsonify,
    make_response,
    send_from_directory,
    current_app,
)
from werkzeug.utils import secure_filename
from models import (
    Faculty,
    Department,
    Major,
    User,
    SystemSettings,
    FacultyScoreSettings,
    Student,
    Application,
    GraduateFile,
)
from datetime import datetime
from extensions import db

# 引入组织信息管理模块
from .organization_bp import (
    get_all_faculties,
    get_departments_by_faculty_id,
    get_all_departments,
    get_all_majors,
    get_majors_by_department_id,
    get_majors_by_faculty_id,
)

# 创建蓝图实例
admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


# 获取所有学院
@admin_bp.route("/faculties", methods=["GET"])
def get_faculties():
    # 使用通用函数获取学院列表（管理员接口需要详细信息）
    faculties = get_all_faculties(detailed=True)
    return make_response(jsonify({"faculties": faculties}), 200)


# 创建学院
@admin_bp.route("/faculties", methods=["POST"])
def create_faculty():
    data = request.get_json()

    # 检查学院是否已存在
    existing_faculty = Faculty.query.filter_by(name=data["name"]).first()
    if existing_faculty:
        return jsonify({"message": "学院已存在"}), 400

    # 创建新学院
    new_faculty = Faculty(name=data["name"], description=data.get("description", ""))

    db.session.add(new_faculty)
    db.session.commit()

    # 创建默认的学院成绩比例设置
    default_settings = FacultyScoreSettings(faculty_id=new_faculty.id)
    db.session.add(default_settings)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "学院创建成功",
                "faculty": {
                    "id": new_faculty.id,
                    "name": new_faculty.name,
                    "description": new_faculty.description,
                },
            }
        ),
        201,
    )


# 更新学院
@admin_bp.route("/faculties/<int:faculty_id>", methods=["PUT"])
def update_faculty(faculty_id):
    data = request.get_json()
    faculty = Faculty.query.get(faculty_id)

    if not faculty:
        return jsonify({"message": "学院不存在"}), 404

    # 检查学院名称是否已被其他学院使用
    existing_faculty = (
        Faculty.query.filter_by(name=data["name"])
        .filter(Faculty.id != faculty_id)
        .first()
    )
    if existing_faculty:
        return jsonify({"message": "学院名称已存在"}), 400

    faculty.name = data["name"]
    faculty.description = data.get("description", "")

    db.session.commit()

    return (
        jsonify(
            {
                "message": "学院更新成功",
                "faculty": {
                    "id": faculty.id,
                    "name": faculty.name,
                    "description": faculty.description,
                },
            }
        ),
        200,
    )


# 删除学院
@admin_bp.route("/faculties/<int:faculty_id>", methods=["DELETE"])
def delete_faculty(faculty_id):
    current_app.logger.info(f"管理员开始删除学院，学院ID: {faculty_id}")

    faculty = Faculty.query.get(faculty_id)

    if not faculty:
        current_app.logger.warning(f"尝试删除不存在的学院，学院ID: {faculty_id}")
        return jsonify({"message": "学院不存在"}), 404

    current_app.logger.info(f"待删除学院: {faculty.name}")

    # 删除学院成绩比例设置
    score_settings = FacultyScoreSettings.query.filter_by(faculty_id=faculty_id).first()
    if score_settings:
        current_app.logger.info(f"删除学院成绩比例设置: {score_settings.id}")
        db.session.delete(score_settings)

    # 级联删除：推免申请 ->学生 ->用户 ->专业 ->系 -> 学院

    # 1. 先获取所有关联的申请记录
    applications = Application.query.filter_by(faculty_id=faculty.id).all()
    current_app.logger.info(f"将删除{len(applications)}个关联的推免申请")
    for application in applications:
        # 删除申请关联的文件
        if application.files:
            for file in application.files:
                try:
                    if "path" in file and file["path"]:
                        filename = os.path.basename(file["path"])
                        file_path = os.path.join(
                            current_app.config["FILE_FOLDER"], filename
                        )
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            current_app.logger.info(f"删除推免申请附件: {file_path}")
                except Exception as e:
                    error_msg = f"删除文件失败: {str(e)}"
                    current_app.logger.error(error_msg)
                    print(error_msg)
        db.session.delete(application)

    # 2. 再获取所有关联的学生，通过直接关联的方式
    students = Student.query.filter_by(faculty_id=faculty.id).all()
    current_app.logger.info(f"将处理{len(students)}个关联的学生")
    for student in students:
        # 删除关联的用户记录
        if student.user:
            current_app.logger.info(
                f"删除学生用户: {student.user.id} ({student.user.username})"
            )
            db.session.delete(student.user)
        # 删除学生记录
        current_app.logger.info(f"删除学生: {student.id} ({student.student_name})")
        db.session.delete(student)

    # 3. 处理直接关联到学院的非学生用户（如教师、管理员）
    non_student_users = (
        User.query.filter_by(faculty_id=faculty.id).filter(User.role != "student").all()
    )
    if non_student_users:
        current_app.logger.info(f"将清除{len(non_student_users)}个非学生用户的学院关联")
        for user in non_student_users:
            # 清除用户的学院关联，而不是删除用户
            user.faculty_id = None

    # 4. 再获取所有关联的专业
    majors = (
        Major.query.join(Department).filter(Department.faculty_id == faculty.id).all()
    )
    current_app.logger.info(f"将删除{len(majors)}个关联的专业")
    for major in majors:
        db.session.delete(major)

    # 5. 再获取所有关联的系
    departments = Department.query.filter_by(faculty_id=faculty.id).all()
    current_app.logger.info(f"将删除{len(departments)}个关联的系")
    for department in departments:
        db.session.delete(department)

    # 6. 最后删除学院
    current_app.logger.info(f"删除学院: {faculty.id} ({faculty.name})")
    db.session.delete(faculty)

    try:
        db.session.commit()
        current_app.logger.info(f"学院删除成功: {faculty_id}")
        return jsonify({"message": "学院删除成功"}), 200
    except Exception as e:
        db.session.rollback()
        error_msg = f"删除学院失败: {str(e)}"
        current_app.logger.error(error_msg)
        return jsonify({"message": error_msg}), 500


# 获取所有系（可按学院筛选）
@admin_bp.route("/departments", methods=["GET"])
def get_departments():
    faculty_id = request.args.get("faculty_id")

    if faculty_id:
        # 使用通用函数根据学院ID获取系列表（管理员接口需要详细信息）
        departments = get_departments_by_faculty_id(int(faculty_id), detailed=True)

        # 为按学院筛选的结果添加学院名称信息
        faculty_dict = {
            faculty.id: faculty.name
            for faculty in Faculty.query.filter(Faculty.id == faculty_id).all()
        }
        for dept in departments:
            dept["faculty_name"] = faculty_dict.get(dept["faculty_id"], "未知学院")
    else:
        # 使用通用函数获取所有系（管理员接口需要详细信息）
        departments = get_all_departments(detailed=True)

    return make_response(jsonify({"departments": departments}), 200)


# 创建系
@admin_bp.route("/departments", methods=["POST"])
def create_department():
    data = request.get_json()

    # 检查系是否已存在于同一学院
    existing_department = Department.query.filter_by(
        name=data["name"], faculty_id=data["faculty_id"]
    ).first()
    if existing_department:
        return jsonify({"message": "该学院下已存在同名系"}), 400

    # 创建新系
    new_department = Department(
        name=data["name"],
        faculty_id=data["faculty_id"],
        description=data.get("description", ""),
    )

    db.session.add(new_department)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "系创建成功",
                "department": {
                    "id": new_department.id,
                    "name": new_department.name,
                    "faculty_id": new_department.faculty_id,
                    "description": new_department.description,
                },
            }
        ),
        201,
    )


# 更新系
@admin_bp.route("/departments/<int:department_id>", methods=["PUT"])
def update_department(department_id):
    data = request.get_json()
    department = Department.query.get(department_id)

    if not department:
        return jsonify({"message": "系不存在"}), 404

    # 检查系名称是否已被同一学院的其他系使用
    existing_department = (
        Department.query.filter_by(name=data["name"], faculty_id=data["faculty_id"])
        .filter(Department.id != department_id)
        .first()
    )
    if existing_department:
        return jsonify({"message": "该学院下已存在同名系"}), 400

    department.name = data["name"]
    department.faculty_id = data["faculty_id"]
    department.description = data.get("description", "")

    db.session.commit()

    return (
        jsonify(
            {
                "message": "系更新成功",
                "department": {
                    "id": department.id,
                    "name": department.name,
                    "faculty_id": department.faculty_id,
                    "description": department.description,
                },
            }
        ),
        200,
    )


# 删除系
@admin_bp.route("/departments/<int:department_id>", methods=["DELETE"])
def delete_department(department_id):
    department = Department.query.get(department_id)

    if not department:
        return jsonify({"message": "系不存在"}), 404

    # 级联删除：系 -> 专业 -> 学生 -> 用户
    from models import Student, Major, Application

    # 1. 先获取所有关联的申请记录
    applications = Application.query.filter_by(department_id=department.id).all()
    for application in applications:
        # 删除申请关联的文件
        if application.files:
            for file in application.files:
                try:
                    if "path" in file and file["path"]:
                        filename = os.path.basename(file["path"])
                        file_path = os.path.join(
                            current_app.config["FILE_FOLDER"], filename
                        )
                        if os.path.exists(file_path):
                            os.remove(file_path)
                except Exception as e:
                    print(f"删除文件失败: {str(e)}")
        db.session.delete(application)

    # 2. 再获取所有关联的学生
    students = Student.query.filter_by(department_id=department.id).all()
    for student in students:
        # 删除关联的用户记录
        if student.user:
            db.session.delete(student.user)
        # 删除学生记录
        db.session.delete(student)

    # 3. 再获取所有关联的专业
    majors = Major.query.filter_by(department_id=department.id).all()
    for major in majors:
        db.session.delete(major)

    # 4. 最后删除系
    db.session.delete(department)

    try:
        db.session.commit()
        return jsonify({"message": "系删除成功"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"删除系失败: {str(e)}"}), 500


# 获取所有专业（可按学院或系筛选）
@admin_bp.route("/majors", methods=["GET"])
def get_majors():
    department_id = request.args.get("department_id")
    faculty_id = request.args.get("faculty_id")

    # 使用通用函数获取专业列表（管理员接口需要详细信息）
    if department_id:
        majors = get_majors_by_department_id(int(department_id), detailed=True)
    elif faculty_id:
        majors = get_majors_by_faculty_id(int(faculty_id), detailed=True)
    else:
        majors = get_all_majors(detailed=True)
    return make_response(jsonify({"majors": majors}), 200)


# 创建专业
@admin_bp.route("/majors", methods=["POST"])
def create_major():
    data = request.get_json()

    # 检查专业是否已存在于同系
    existing_major = Major.query.filter_by(
        name=data["name"], department_id=data["department_id"]
    ).first()
    if existing_major:
        return jsonify({"message": "该系下已存在同名专业"}), 400

    # 创建新专业
    new_major = Major(
        name=data["name"],
        department_id=data["department_id"],
        description=data.get("description", ""),
    )

    db.session.add(new_major)
    db.session.commit()

    return (
        jsonify(
            {
                "message": "专业创建成功",
                "major": {
                    "id": new_major.id,
                    "name": new_major.name,
                    "department_id": new_major.department_id,
                    "description": new_major.description,
                },
            }
        ),
        201,
    )


# 更新专业
@admin_bp.route("/majors/<int:major_id>", methods=["PUT"])
def update_major(major_id):
    data = request.get_json()
    major = Major.query.get(major_id)

    if not major:
        return jsonify({"message": "专业不存在"}), 404

    # 检查专业名称是否已被同系的其他专业使用
    existing_major = (
        Major.query.filter_by(name=data["name"], department_id=data["department_id"])
        .filter(Major.id != major_id)
        .first()
    )
    if existing_major:
        return jsonify({"message": "该系下已存在同名专业"}), 400

    major.name = data["name"]
    major.department_id = data["department_id"]
    major.description = data.get("description", "")

    db.session.commit()

    return (
        jsonify(
            {
                "message": "专业更新成功",
                "major": {
                    "id": major.id,
                    "name": major.name,
                    "department_id": major.department_id,
                    "description": major.description,
                },
            }
        ),
        200,
    )


# 删除专业
@admin_bp.route("/majors/<int:major_id>", methods=["DELETE"])
def delete_major(major_id):
    major = Major.query.get(major_id)

    if not major:
        return jsonify({"message": "专业不存在"}), 404

    # 级联删除：专业 -> 申请记录 -> 学生 -> 用户
    from models import Student, Application

    # 1. 先获取所有关联的申请记录
    applications = Application.query.filter_by(major_id=major.id).all()
    for application in applications:
        # 删除申请关联的文件
        if application.files:
            for file in application.files:
                try:
                    if "path" in file and file["path"]:
                        filename = os.path.basename(file["path"])
                        file_path = os.path.join(
                            current_app.config["FILE_FOLDER"], filename
                        )
                        if os.path.exists(file_path):
                            os.remove(file_path)
                except Exception as e:
                    print(f"删除文件失败: {str(e)}")
        db.session.delete(application)

    # 2. 再获取所有关联的学生
    students = Student.query.filter_by(major_id=major.id).all()
    for student in students:
        # 删除关联的用户记录
        if student.user:
            db.session.delete(student.user)
        # 删除学生记录
        db.session.delete(student)

    # 3. 最后删除专业
    db.session.delete(major)

    try:
        db.session.commit()
        return jsonify({"message": "专业删除成功"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"删除专业失败: {str(e)}"}), 500


# 获取系统设置
@admin_bp.route("/system-settings", methods=["GET"])
def get_system_settings():
    # 获取唯一的系统设置记录，如果不存在则创建默认记录
    settings = SystemSettings.query.first()
    if not settings:
        # 创建默认设置
        settings = SystemSettings()
        db.session.add(settings)
        db.session.commit()

    # 转换为JSON格式
    settings_data = {
        "academicYear": settings.academic_year,
        "applicationStart": (
            settings.application_start.isoformat()
            if settings.application_start
            else None
        ),
        "applicationEnd": (
            settings.application_end.isoformat() if settings.application_end else None
        ),
        "singleFileSizeLimit": settings.single_file_size_limit,
        "totalFileSizeLimit": settings.total_file_size_limit,
        "avatarFileSizeLimit": settings.avatar_file_size_limit,
        "allowedFileTypes": settings.allowed_file_types,
        "systemStatus": settings.system_status,
        "lastBackup": (
            settings.last_backup.isoformat() if settings.last_backup else None
        ),
    }

    return jsonify({"settings": settings_data}), 200


# 更新系统设置
@admin_bp.route("/system-settings", methods=["PUT"])
def update_system_settings():
    data = request.get_json()
    current_app.logger.info("管理员开始更新系统设置")

    # 记录更新的设置项
    update_fields = list(data.keys())
    current_app.logger.info(f"将更新的设置项: {update_fields}")

    # 获取唯一的系统设置记录，如果不存在则创建
    settings = SystemSettings.query.first()
    if not settings:
        settings = SystemSettings()
        db.session.add(settings)
        current_app.logger.info("创建了新的系统设置记录")

    # 更新设置
    if "academicYear" in data:
        old_value = settings.academic_year
        settings.academic_year = data["academicYear"]
        current_app.logger.info(f"更新学年: {old_value} -> {data['academicYear']}")

    if "applicationStart" in data and data["applicationStart"]:
        old_value = (
            settings.application_start.isoformat()
            if settings.application_start
            else None
        )
        settings.application_start = datetime.fromisoformat(data["applicationStart"])
        current_app.logger.info(
            f"更新申请开始时间: {old_value} -> {data['applicationStart']}"
        )

    if "applicationEnd" in data and data["applicationEnd"]:
        old_value = (
            settings.application_end.isoformat() if settings.application_end else None
        )
        settings.application_end = datetime.fromisoformat(data["applicationEnd"])
        current_app.logger.info(
            f"更新申请结束时间: {old_value} -> {data['applicationEnd']}"
        )

    if "systemStatus" in data:
        old_value = settings.system_status
        settings.system_status = data["systemStatus"]
        current_app.logger.info(f"更新系统状态: {old_value} -> {data['systemStatus']}")

    # 记录其他设置的更新
    size_settings = ["singleFileSizeLimit", "totalFileSizeLimit", "avatarFileSizeLimit"]
    for setting in size_settings:
        if setting in data:
            # 将驼峰式命名转换为下划线命名
            model_attr = setting.replace('FileSize', '_file_size').replace('Limit', '_limit').lower()
            old_value = getattr(settings, model_attr)
            setattr(settings, model_attr, data[setting])
            current_app.logger.info(f"更新{setting}: {old_value} -> {data[setting]}")

    if "allowedFileTypes" in data:
        old_value = settings.allowed_file_types
        settings.allowed_file_types = data["allowedFileTypes"]
        current_app.logger.info(
            f"更新允许的文件类型: {old_value} -> {data['allowedFileTypes']}"
        )

    if "lastBackup" in data and data["lastBackup"]:
        old_value = settings.last_backup.isoformat() if settings.last_backup else None
        settings.last_backup = datetime.fromisoformat(data["lastBackup"])
        current_app.logger.info(
            f"更新最后备份时间: {old_value} -> {data['lastBackup']}"
        )

    db.session.commit()
    current_app.logger.info("系统设置更新完成")

    # 返回更新后的设置
    updated_settings = {
        "academicYear": settings.academic_year,
        "applicationStart": (
            settings.application_start.isoformat()
            if settings.application_start
            else None
        ),
        "applicationEnd": (
            settings.application_end.isoformat() if settings.application_end else None
        ),
        "singleFileSizeLimit": settings.single_file_size_limit,
        "totalFileSizeLimit": settings.total_file_size_limit,
        "avatarFileSizeLimit": settings.avatar_file_size_limit,
        "allowedFileTypes": settings.allowed_file_types,
        "systemStatus": settings.system_status,
        "lastBackup": (
            settings.last_backup.isoformat() if settings.last_backup else None
        ),
    }

    return jsonify({"message": "系统设置更新成功", "settings": updated_settings}), 200


# 获取所有学院的成绩设置
@admin_bp.route("/faculty-score-settings", methods=["GET"])
def get_faculty_score_settings():
    # 获取所有学院的成绩设置
    settings = FacultyScoreSettings.query.all()

    # 转换为JSON格式
    settings_data = []
    for setting in settings:
        settings_data.append(
            {
                "id": setting.id,
                "faculty_id": setting.faculty_id,
                "faculty_name": setting.faculty.name,
                "academic_score_weight": setting.academic_score_weight,
                "specialty_max_score": setting.specialty_max_score,
                "performance_max_score": setting.performance_max_score,
            }
        )

    return jsonify({"settings": settings_data}), 200


# 获取特定学院的成绩设置
@admin_bp.route("/faculty-score-settings/<int:faculty_id>", methods=["GET"])
def get_faculty_score_setting(faculty_id):
    # 获取特定学院的成绩设置，如果不存在则创建默认设置
    setting = FacultyScoreSettings.query.filter_by(faculty_id=faculty_id).first()
    if not setting:
        # 检查学院是否存在
        faculty = Faculty.query.get(faculty_id)
        if not faculty:
            return jsonify({"message": "学院不存在"}), 404

        # 创建默认设置
        setting = FacultyScoreSettings(faculty_id=faculty_id)
        db.session.add(setting)
        db.session.commit()

    # 转换为JSON格式
    settings_data = {
        "id": setting.id,
        "faculty_id": setting.faculty_id,
        "faculty_name": setting.faculty.name,
        "academic_score_weight": setting.academic_score_weight,
        "specialty_max_score": setting.specialty_max_score,
        "performance_max_score": setting.performance_max_score,
    }

    return jsonify({"settings": settings_data}), 200


# 更新学院的成绩设置
@admin_bp.route("/faculty-score-settings/<int:faculty_id>", methods=["PUT"])
def update_faculty_score_setting(faculty_id):
    data = request.get_json()

    # 获取特定学院的成绩设置，如果不存在则创建
    setting = FacultyScoreSettings.query.filter_by(faculty_id=faculty_id).first()
    if not setting:
        # 检查学院是否存在
        faculty = Faculty.query.get(faculty_id)
        if not faculty:
            return jsonify({"message": "学院不存在"}), 404

        setting = FacultyScoreSettings(faculty_id=faculty_id)
        db.session.add(setting)

    # 更新设置
    if "academic_score_weight" in data:
        setting.academic_score_weight = data["academic_score_weight"]

    if "specialty_max_score" in data:
        setting.specialty_max_score = data["specialty_max_score"]

    if "performance_max_score" in data:
        setting.performance_max_score = data["performance_max_score"]

    db.session.commit()

    # 返回更新后的设置
    updated_settings = {
        "id": setting.id,
        "faculty_id": setting.faculty_id,
        "faculty_name": setting.faculty.name,
        "academic_score_weight": setting.academic_score_weight,
        "specialty_max_score": setting.specialty_max_score,
        "performance_max_score": setting.performance_max_score,
    }

    return (
        jsonify({"message": "学院成绩设置更新成功", "settings": updated_settings}),
        200,
    )


# 推免相关文件管理API


# 上传推免相关文件
@admin_bp.route("/graduate-files", methods=["POST"])
def upload_graduate_file():
    from flask import current_app  # 使用current_app代替直接导入app实例

    # 检查是否有文件部分
    if "file" not in request.files:
        return jsonify({"message": "没有文件部分"}), 400

    file = request.files["file"]

    # 检查文件名是否为空
    if file.filename == "":
        return jsonify({"message": "没有选择文件"}), 400

    # 检查文件是否允许上传
    if file:
        # 保留原始文件名
        original_filename = file.filename
        # 从原始文件名中提取扩展名
        file_ext = os.path.splitext(original_filename)[1]
        # 生成唯一的文件名用于存储（UUID+扩展名）
        unique_filename = f"{uuid.uuid4()}{file_ext}"

        # 创建专门的推免文件目录
        GRADUATE_FILES_FOLDER = os.path.join(
            current_app.config["UPLOAD_FOLDER"], "graduate-files"
        )

        # 确保上传目录存在
        if not os.path.exists(GRADUATE_FILES_FOLDER):
            os.makedirs(GRADUATE_FILES_FOLDER)

        # 保存文件
        file_path = os.path.join(GRADUATE_FILES_FOLDER, unique_filename)
        file.save(file_path)
        current_app.logger.info(
            f"管理员上传推免文件: {original_filename} 大小: {os.path.getsize(file_path)} bytes"
        )

        # 从请求中获取其他信息
        uploader = request.form.get("uploader", "admin")
        description = request.form.get("description", "")
        category = request.form.get("category", "graduate")
        faculty_id = request.form.get("faculty_id", type=int)

        faculty_info = f"学院ID: {faculty_id}" if faculty_id else "无指定学院"
        current_app.logger.info(
            f"文件信息 - 上传者: {uploader}, 类别: {category}, {faculty_info}"
        )

        # 创建文件记录 - 合并filename和original_filename字段
        # filename字段现在只存储原始文件名，从filepath中提取文件系统中的文件名
        graduate_file = GraduateFile(
            filename=original_filename,  # 只存储原始文件名
            filepath=file_path,
            file_size=os.path.getsize(file_path),
            file_type=file.mimetype,
            uploader=uploader,
            description=description,
            category=category,
            faculty_id=faculty_id,
        )

        # 保存到数据库
        from extensions import db

        db.session.add(graduate_file)
        db.session.commit()
        current_app.logger.info(f"推免文件上传完成，文件ID: {graduate_file.id}")

        return (
            jsonify(
                {
                    "message": "文件上传成功",
                    "file": {
                        "id": graduate_file.id,
                        "filename": original_filename,  # 返回原始文件名用于前端显示
                        "file_size": graduate_file.file_size,
                        "file_type": graduate_file.file_type,
                        "upload_time": graduate_file.upload_time.isoformat(),
                        "uploader": graduate_file.uploader,
                        "description": graduate_file.description,
                        "category": graduate_file.category,
                    },
                }
            ),
            201,
        )


# 获取所有推免相关文件
@admin_bp.route("/graduate-files", methods=["GET"])
def get_graduate_files():
    # 获取所有推免相关文件，并预加载学院信息
    graduate_files = GraduateFile.query.options(
        db.joinedload(GraduateFile.faculty)
    ).all()

    # 转换为JSON格式
    files_data = []
    for file in graduate_files:
        # 从filepath中提取文件系统中的文件名用于下载链接
        file_system_filename = os.path.basename(file.filepath)

        # 学院信息
        faculty_info = (
            {"id": file.faculty.id, "name": file.faculty.name} if file.faculty else None
        )

        files_data.append(
            {
                "id": file.id,
                "filename": file.filename,  # 原始文件名（用于显示和下载）
                "file_url": f"/uploads/graduate-files/{file_system_filename}",  # 下载链接
                "file_size": file.file_size,
                "file_type": file.file_type,
                "upload_time": file.upload_time.isoformat(),
                "uploader": file.uploader,
                "description": file.description,
                "category": file.category,
                "faculty": faculty_info,
            }
        )

    return jsonify({"files": files_data}), 200


# 删除推免相关文件
@admin_bp.route("/graduate-files/<int:file_id>", methods=["DELETE"])
def delete_graduate_file(file_id):
    from flask import current_app  # 使用current_app代替直接导入app实例

    current_app.logger.info(f"管理员开始删除推免文件，文件ID: {file_id}")

    # 查找文件
    graduate_file = GraduateFile.query.get(file_id)
    if not graduate_file:
        current_app.logger.warning(f"尝试删除不存在的推免文件，文件ID: {file_id}")
        return jsonify({"message": "文件不存在"}), 404

    # 记录文件信息
    file_info = f"文件名: {graduate_file.filename}, 文件路径: {graduate_file.filepath}, 大小: {graduate_file.file_size} bytes"
    current_app.logger.info(f"待删除文件信息: {file_info}")

    # 删除物理文件
    try:
        os.remove(graduate_file.filepath)
        current_app.logger.info(f"成功删除物理文件: {graduate_file.filepath}")
    except Exception as e:
        error_msg = f"删除文件失败: {str(e)}"
        current_app.logger.error(error_msg)
        print(error_msg)

    # 删除数据库记录
    from extensions import db

    db.session.delete(graduate_file)
    db.session.commit()
    current_app.logger.info(f"成功删除推免文件记录，文件ID: {file_id}")

    return jsonify({"message": "文件删除成功"}), 200


# 前端获取推免相关文件（无需登录）
@admin_bp.route("/public/graduate-files", methods=["GET"])
def get_public_graduate_files():
    # 获取请求参数中的学院ID
    faculty_id = request.args.get("facultyId", type=int)

    # 构建查询
    query = GraduateFile.query.options(db.joinedload(GraduateFile.faculty))

    # 根据学院ID过滤文件
    if faculty_id:
        query = query.filter_by(faculty_id=faculty_id)

    # 执行查询
    graduate_files = query.all()

    # 转换为JSON格式
    files_data = []
    for file in graduate_files:
        # 从filepath中提取文件系统中的文件名用于下载链接
        file_system_filename = os.path.basename(file.filepath)

        # 学院信息
        faculty_info = (
            {"id": file.faculty.id, "name": file.faculty.name} if file.faculty else None
        )

        files_data.append(
            {
                "id": file.id,
                "filename": file.filename,  # 原始文件名（用于显示和下载）
                "file_url": f"/uploads/graduate-files/{file_system_filename}",  # 下载链接
                "file_size": file.file_size,
                "file_type": file.file_type,
                "upload_time": file.upload_time.isoformat(),
                "description": file.description,
                "category": file.category,
                "faculty": faculty_info,
            }
        )

    return jsonify({"files": files_data}), 200
