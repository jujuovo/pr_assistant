# -*- coding: utf-8 -*-
"""
申请管理蓝图

该文件负责处理申请管理相关的API端点，包括：
- 获取所有申请
- 获取单个申请
- 创建申请
- 更新申请
- 审核申请
- 删除申请
- 获取待审核申请
"""

from flask import Blueprint, request, jsonify, current_app
from models import Application, Student, Rule, Department, Major, SystemSettings
from datetime import datetime
import pytz
import json
import os
import traceback
import uuid
from extensions import db
from blueprints.score_bp import update_student_statistics

# 创建蓝图实例
application_bp = Blueprint("application", __name__, url_prefix="/api")


# 获取所有申请
@application_bp.route("/applications", methods=["GET"])
def get_applications():
    # 获取查询参数
    student_id = request.args.get("studentId")
    student_name = request.args.get("studentName")
    status = request.args.get("status")
    application_type = request.args.get("applicationType")
    reviewed_by = request.args.get("reviewedBy")
    reviewed_start_date = request.args.get("reviewedStartDate")
    reviewed_end_date = request.args.get("reviewedEndDate")
    faculty_id = request.args.get("facultyId")
    department_id = request.args.get("departmentId")
    major_id = request.args.get("majorId")
    department_name = request.args.get("department")
    major_name = request.args.get("major")

    # 构建查询
    query = Application.query

    # 按学院筛选
    if faculty_id:
        query = query.filter_by(faculty_id=faculty_id)

    if student_id:
        query = query.filter_by(student_id=student_id)

    if student_name:
        query = query.filter(Application.student_name.like(f"%{student_name}%"))

    if status:
        query = query.filter_by(status=status)

    if application_type:
        query = query.filter_by(application_type=application_type)

    if reviewed_by:
        query = query.filter(Application.reviewed_by.like(f"%{reviewed_by}%"))

    if department_id:
        query = query.filter_by(department_id=department_id)
    elif department_name:
        # 按系名称筛选（支持部分匹配）

        # 先根据名称获取所有匹配的系ID
        departments = Department.query.filter(
            Department.name.like(f"%{department_name}%")
        ).all()
        if departments:
            department_ids = [dept.id for dept in departments]
            query = query.filter(Application.department_id.in_(department_ids))

    if major_id:
        query = query.filter_by(major_id=major_id)
    elif major_name:
        # 按专业名称筛选（支持部分匹配）

        # 先根据名称获取所有匹配的专业ID
        majors = Major.query.filter(Major.name.like(f"%{major_name}%")).all()
        if majors:
            major_ids = [major.id for major in majors]
            query = query.filter(Application.major_id.in_(major_ids))

    # 审核时间筛选
    if reviewed_start_date:
        try:
            # 转换为datetime对象
            start_date = datetime.fromisoformat(reviewed_start_date)
            query = query.filter(Application.reviewed_at >= start_date)
        except (ValueError, TypeError):
            # 如果日期格式无效，忽略该筛选条件
            pass

    if reviewed_end_date:
        try:
            # 转换为datetime对象，并设置为当天结束时间
            end_date = datetime.fromisoformat(reviewed_end_date)
            end_date = end_date.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
            query = query.filter(Application.reviewed_at <= end_date)
        except (ValueError, TypeError):
            # 如果日期格式无效，忽略该筛选条件
            pass

    applications = query.all()
    app_list = []

    # 获取所有相关系、专业和规则信息以避免N+1查询问题

    department_ids = {app.department_id for app in applications}
    departments = Department.query.filter(Department.id.in_(department_ids)).all()
    department_dict = {d.id: d.name for d in departments}

    major_ids = {app.major_id for app in applications}
    majors = Major.query.filter(Major.id.in_(major_ids)).all()
    major_dict = {m.id: m.name for m in majors}

    # 获取所有规则信息
    rule_ids = {app.rule_id for app in applications if app.rule_id}
    rules = Rule.query.filter(Rule.id.in_(rule_ids)).all()

    # 获取所有规则的计算配置
    from models import RuleCalculation

    rule_calculations = RuleCalculation.query.filter(
        RuleCalculation.rule_id.in_(rule_ids)
    ).all()
    calculation_dict = {calc.rule_id: calc for calc in rule_calculations}

    rule_dict = {
        r.id: {
            "id": r.id,
            "name": r.name,
            "score": r.score,
            "description": r.description,
            "calculation": (
                {
                    "id": calculation_dict[r.id].id,
                    "rule_id": calculation_dict[r.id].rule_id,
                    "calculation_type": calculation_dict[r.id].calculation_type,
                    "formula": calculation_dict[r.id].formula,
                    "parameters": calculation_dict[r.id].parameters,
                    "max_score": calculation_dict[r.id].max_score,
                }
                if r.id in calculation_dict
                else None
            ),
        }
        for r in rules
    }

    for app in applications:
        # 转换文件路径格式
        processed_files = []
        if app.files:
            for file in app.files:
                # 确保processed_file是字典类型以便处理
                if isinstance(file, dict):
                    processed_file = file.copy()
                    # 保留原文件的size字段
                    if "size" in file:
                        processed_file["size"] = file["size"]

                    # 如果是本地绝对路径，转换为相对URL
                    if "path" in processed_file and os.path.isabs(
                        processed_file["path"]
                    ):
                        # 从绝对路径中提取文件名和子文件夹
                        filename = os.path.basename(processed_file["path"])
                        # 判断文件应该属于哪个子文件夹
                        if "avatars" in processed_file["path"]:
                            processed_file["path"] = f"/uploads/avatars/{filename}"
                        else:
                            # 默认将其他文件归类到files文件夹
                            processed_file["path"] = f"/uploads/files/{filename}"
                else:
                    # 如果file不是字典类型，尝试将其转换为字典
                    try:
                        processed_file = dict(file)
                    except:
                        # 如果转换失败，使用默认空字典
                        processed_file = {}
                processed_files.append(processed_file)

        app_data = {
            "id": app.id,
            "studentId": app.student_id,
            "studentName": app.student_name,
            "facultyId": app.faculty_id,
            "departmentId": app.department_id,
            "department": department_dict.get(app.department_id, "未知系"),
            "majorId": app.major_id,
            "major": major_dict.get(app.major_id, "未知专业"),
            "applicationType": app.application_type,
            "appliedAt": app.applied_at.isoformat() if app.applied_at else None,
            "selfScore": app.self_score,
            "finalScore": app.final_score,
            "status": app.status,
            "reviewComment": app.review_comment,
            "reviewedAt": app.reviewed_at.isoformat() if app.reviewed_at else None,
            "reviewedBy": app.reviewed_by,
            "projectName": app.project_name,
            "awardDate": app.award_date.isoformat() if app.award_date else None,
            "description": app.description,
            "files": processed_files,
            "finalScore": app.final_score,
            "reviewComment": app.review_comment,
            "reviewedAt": app.reviewed_at.isoformat() if app.reviewed_at else None,
            "reviewedBy": app.reviewed_by,
            # 规则相关字段
            "ruleId": app.rule_id,
            "rule": rule_dict.get(app.rule_id) if app.rule_id else None,
            # 动态系数字段
            "dynamicCoefficients": app.dynamic_coefficients,
        }
        app_list.append(app_data)

    return jsonify(app_list), 200


# 获取单个申请
@application_bp.route("/applications/<int:id>", methods=["GET"])
def get_application(id):
    app = Application.query.get_or_404(id)

    # 转换文件路径格式
    processed_files = []
    if app.files:
        for file in app.files:
            # 确保processed_file是字典类型以便处理
            if isinstance(file, dict):
                processed_file = file.copy()
                # 保留原文件的size字段
                if "size" in file:
                    processed_file["size"] = file["size"]

                # 如果是本地绝对路径，转换为相对URL
                if "path" in processed_file and os.path.isabs(processed_file["path"]):
                    # 从绝对路径中提取文件名和子文件夹
                    filename = os.path.basename(processed_file["path"])
                    # 判断文件应该属于哪个子文件夹
                    if "avatars" in processed_file["path"]:
                        processed_file["path"] = f"/uploads/avatars/{filename}"
                    else:
                        # 默认将其他文件归类到files文件夹
                        processed_file["path"] = f"/uploads/files/{filename}"
            else:
                # 如果file不是字典类型，尝试将其转换为字典
                try:
                    processed_file = dict(file)
                except:
                    # 如果转换失败，使用默认空字典
                    processed_file = {}
            processed_files.append(processed_file)

    # 获取相关系、专业和规则信息

    # 安全获取系和专业名称
    department = Department.query.get(app.department_id) if app.department_id else None
    department_name = department.name if department else "未知系"

    major = Major.query.get(app.major_id) if app.major_id else None
    major_name = major.name if major else "未知专业"

    # 获取规则信息
    rule_info = None
    if app.rule_id:
        rule = Rule.query.get(app.rule_id)
        if rule:
            # 获取规则的计算配置
            from models import RuleCalculation

            calculation = RuleCalculation.query.filter_by(rule_id=app.rule_id).first()
            calculation_data = None
            if calculation:
                calculation_data = {
                    "id": calculation.id,
                    "rule_id": calculation.rule_id,
                    "calculation_type": calculation.calculation_type,
                    "formula": calculation.formula,
                    "parameters": calculation.parameters,
                    "max_score": calculation.max_score,
                }
            rule_info = {
                "id": rule.id,
                "name": rule.name,
                "score": rule.score,
                "description": rule.description,
                "calculation": calculation_data,
            }

    app_data = {
        "id": app.id,
        "studentId": app.student_id,
        "studentName": app.student_name,
        "departmentId": app.department_id,
        "department": department_name,
        "majorId": app.major_id,
        "major": major_name,
        "applicationType": app.application_type,
        "appliedAt": app.applied_at.isoformat() if app.applied_at else None,
        "selfScore": app.self_score,
        "status": app.status,
        "projectName": app.project_name,
        "awardDate": app.award_date.isoformat() if app.award_date else None,
        "description": app.description,
        "files": processed_files,
        "dynamicCoefficients": app.dynamic_coefficients,
        "finalScore": app.final_score,
        "reviewComment": app.review_comment,
        "reviewedAt": app.reviewed_at.isoformat() if app.reviewed_at else None,
        "reviewedBy": app.reviewed_by,
        # 规则相关字段
        # 规则相关字段
        "ruleId": app.rule_id,
        "rule": rule_info,
    }

    return jsonify(app_data), 200


# 创建申请
@application_bp.route("/applications", methods=["POST"])
def create_application():
    try:
        # 解析申请数据
        if "application" in request.form:
            data = json.loads(request.form["application"])
        else:
            data = request.get_json()

        # 字段名转换：将前端的驼峰式命名转换为后端的下划线命名
        field_mapping = {
            "studentId": "student_id",
            "studentName": "student_name",
            "name": "student_name",  # 兼容前端可能使用的name字段
            "facultyId": "faculty_id",
            "departmentId": "department_id",
            "majorId": "major_id",
            "applicationType": "application_type",
            "selfScore": "self_score",
            "projectName": "project_name",
            "awardDate": "award_date",
            "ruleId": "rule_id",
            "finalScore": "final_score",
            "reviewComment": "review_comment",
            "reviewedAt": "reviewed_at",
            "reviewedBy": "reviewed_by",
            "appliedAt": "applied_at",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
            "dynamicCoefficients": "dynamic_coefficients",
        }

        # 转换数据字段
        transformed_data = {}
        for key, value in data.items():
            # 使用映射的字段名，如果没有映射则使用原字段名
            new_key = field_mapping.get(key, key)
            # 处理数值类型字段：将空字符串转换为None
            numeric_fields = ["self_score", "final_score", "rule_id"]
            if new_key in numeric_fields and value == "":
                transformed_data[new_key] = None
            else:
                transformed_data[new_key] = value

        # 使用转换后的数据
        data = transformed_data

        # 验证项目名称长度
        if "project_name" in data and (len(data["project_name"]) < 2 or len(data["project_name"]) > 50):
            return jsonify({"error": "项目名称长度必须在2-50个字符之间"}), 400

        # 处理文件上传
        files = []
        if request.files:
            # 获取系统设置中的文件大小限制和允许的文件类型
            settings = SystemSettings.query.first()
            if not settings:
                return jsonify({"error": "系统设置未配置"}), 500

            single_file_size_limit = (
                settings.single_file_size_limit * 1024 * 1024
            )  # 转换为字节
            total_file_size_limit = (
                settings.total_file_size_limit * 1024 * 1024
            )  # 转换为字节
            allowed_file_types = settings.allowed_file_types

            # 创建上传目录（如果不存在）
            if not os.path.exists(current_app.config["UPLOAD_FOLDER"]):
                os.makedirs(current_app.config["UPLOAD_FOLDER"])

            # 确保文件上传目录存在
            if not os.path.exists(current_app.config["FILE_FOLDER"]):
                os.makedirs(current_app.config["FILE_FOLDER"])

            total_upload_size = 0
            # 保存文件并记录信息
            for file in request.files.getlist("files"):
                if file and file.filename:
                    # 检查文件类型
                    file_ext = os.path.splitext(file.filename)[1].lower()
                    # 将允许的文件类型字符串转换为列表
                    allowed_types_list = [
                        ext.strip().lower() for ext in allowed_file_types.split(",")
                    ]
                    if file_ext not in allowed_types_list:
                        return (
                            jsonify(
                                {
                                    "error": f"文件类型不允许: {file.filename}，仅支持{allowed_file_types}"
                                }
                            ),
                            400,
                        )

                    # 检查单个文件大小
                    file.seek(0, 2)  # 移动到文件末尾
                    file_size = file.tell()  # 获取文件大小
                    file.seek(0)  # 重置文件指针到开头

                    if file_size > single_file_size_limit:
                        return (
                            jsonify(
                                {
                                    "error": f"单个文件大小超过限制: {file.filename}，最大允许{settings.single_file_size_limit}MB"
                                }
                            ),
                            400,
                        )

                    # 检查总文件大小
                    total_upload_size += file_size
                    if total_upload_size > total_file_size_limit:
                        return (
                            jsonify(
                                {
                                    "error": f"总文件大小超过限制，最大允许{settings.total_file_size_limit}MB"
                                }
                            ),
                            400,
                        )

                    # 生成安全且保留中文的文件名
                    def generate_safe_filename(original_filename):
                        """
                        生成安全的文件名，保留中文等非ASCII字符，确保唯一性
                        """
                        # 分离文件名和扩展名
                        name, ext = os.path.splitext(original_filename)
                        # 生成唯一标识符
                        unique_id = uuid.uuid4().hex[:8]
                        # 使用时间戳和唯一ID确保文件名唯一性
                        timestamp = datetime.now(
                            pytz.timezone("Asia/Shanghai")
                        ).strftime("%Y%m%d%H%M%S")
                        # 保留原始文件名，仅移除路径分隔符防止目录遍历
                        safe_name = name.replace("/", "").replace("\\", "")
                        # 构建最终文件名
                        return f"{safe_name}_{timestamp}_{unique_id}{ext}"

                    # 使用自定义函数生成文件名
                    filename = generate_safe_filename(file.filename)
                    filepath = os.path.join(current_app.config["FILE_FOLDER"], filename)
                    file.save(filepath)

                    # 获取实际文件大小（比file.content_length更可靠）
                    actual_size = os.path.getsize(filepath)

                    # 记录文件信息（存储相对URL而不是本地路径）
                    files.append(
                        {
                            "name": filename,
                            "path": f"/uploads/files/{filename}",
                            "size": actual_size,
                            "type": file.content_type,
                        }
                    )

        # 处理日期字段，允许为空
        award_date_value = None
        if data.get("award_date"):
            award_date_value = datetime.fromisoformat(data["award_date"]).date()

        new_application = Application(
            student_id=data.get("student_id"),
            student_name=data.get("student_name"),
            faculty_id=data.get("faculty_id"),
            department_id=data.get("department_id"),
            major_id=data.get("major_id"),
            application_type=data.get("application_type"),
            applied_at=datetime.now(pytz.timezone("Asia/Shanghai")),
            self_score=data.get("self_score"),
            status=data.get("status", "pending"),
            project_name=data.get("project_name"),
            award_date=award_date_value,
            description=data.get("description"),
            files=files,
            dynamic_coefficients=data.get("dynamic_coefficients"),
            rule_id=data.get("rule_id"),
        )

        db.session.add(new_application)
        db.session.commit()

        # 构建完整的响应数据
        app_data = {
            "id": new_application.id,
            "studentId": new_application.student_id,
            "studentName": new_application.student_name,
            "departmentId": new_application.department_id,
            "department": new_application.department.name,
            "majorId": new_application.major_id,
            "major": new_application.major.name,
            "applicationType": new_application.application_type,
            "appliedAt": (
                new_application.applied_at.isoformat()
                if new_application.applied_at
                else None
            ),
            "selfScore": new_application.self_score,
            "status": new_application.status,
            "projectName": new_application.project_name,
            "awardDate": (
                new_application.award_date.isoformat()
                if new_application.award_date
                else None
            ),
            "description": new_application.description,
            "files": new_application.files,
            "dynamicCoefficients": new_application.dynamic_coefficients,
            "ruleId": new_application.rule_id,
            "message": "申请创建成功",
        }

        return jsonify(app_data), 201
    except json.JSONDecodeError as e:
        return jsonify({"error": "无效的JSON格式", "details": str(e)}), 400
    except KeyError as e:
        return jsonify({"error": f"缺少必要字段: {str(e)}"}), 400
    except ValueError as e:
        return jsonify({"error": f"数据格式错误: {str(e)}"}), 400
    except Exception as e:
        error_msg = f"发生未预期的错误: {str(e)}"
        traceback_str = traceback.format_exc()
        print(error_msg)
        print("详细错误堆栈:")
        print(traceback_str)
        print("请求数据:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return (
            jsonify(
                {
                    "error": "服务器内部错误",
                    "details": str(e),
                    "traceback": traceback_str,
                }
            ),
            500,
        )


# 更新申请
@application_bp.route("/applications/<int:id>", methods=["PUT"])
def update_application(id):
    try:
        application = Application.query.get_or_404(id)

        # 解析申请数据
        if "application" in request.form:
            data = json.loads(request.form["application"])
        else:
            data = request.get_json()

        # 字段名转换：将前端的驼峰式命名转换为后端的下划线命名
        field_mapping = {
            "studentId": "student_id",
            "studentName": "student_name",
            "name": "student_name",  # 兼容前端可能使用的name字段
            "facultyId": "faculty_id",
            "departmentId": "department_id",
            "majorId": "major_id",
            "applicationType": "application_type",
            "selfScore": "self_score",
            "projectName": "project_name",
            "awardDate": "award_date",
            "ruleId": "rule_id",
            "finalScore": "final_score",
            "reviewComment": "review_comment",
            "reviewedAt": "reviewed_at",
            "reviewedBy": "reviewed_by",
            "appliedAt": "applied_at",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        }

        # 转换数据字段
        transformed_data = {}  # 使用新的变量名，避免与原始data冲突
        for key, value in data.items():
            # 使用映射的字段名，如果没有映射则使用原字段名
            new_key = field_mapping.get(key, key)
            # 处理数值类型字段：将空字符串转换为None
            numeric_fields = ["self_score", "final_score", "rule_id"]
            if new_key in numeric_fields and value == "":
                transformed_data[new_key] = None
            else:
                transformed_data[new_key] = value

        # 使用转换后的数据
        data = transformed_data

        # 验证项目名称长度
        if "project_name" in data and (len(data["project_name"]) < 2 or len(data["project_name"]) > 50):
            return jsonify({"error": "项目名称长度必须在2-50个字符之间"}), 400

        # 处理文件上传
        files = []
        if request.files:
            # 获取系统设置中的文件大小限制和允许的文件类型
            settings = SystemSettings.query.first()
            if not settings:
                return jsonify({"error": "系统设置未配置"}), 500

            single_file_size_limit = (
                settings.single_file_size_limit * 1024 * 1024
            )  # 转换为字节
            total_file_size_limit = (
                settings.total_file_size_limit * 1024 * 1024
            )  # 转换为字节
            allowed_file_types = settings.allowed_file_types

            # 创建上传目录（如果不存在）
            if not os.path.exists(current_app.config["UPLOAD_FOLDER"]):
                os.makedirs(current_app.config["UPLOAD_FOLDER"])

            # 确保文件上传目录存在
            if not os.path.exists(current_app.config["FILE_FOLDER"]):
                os.makedirs(current_app.config["FILE_FOLDER"])

            total_upload_size = 0
            # 保存文件并记录信息
            for key, file in request.files.items():
                if file and file.filename:
                    # 检查文件类型
                    file_ext = os.path.splitext(file.filename)[1].lower()
                    # 将允许的文件类型字符串转换为列表
                    allowed_types_list = [
                        ext.strip().lower() for ext in allowed_file_types.split(",")
                    ]
                    if file_ext not in allowed_types_list:
                        return (
                            jsonify(
                                {
                                    "error": f"文件类型不允许: {file.filename}，仅支持{allowed_file_types}"
                                }
                            ),
                            400,
                        )

                    # 检查单个文件大小
                    file.seek(0, 2)  # 移动到文件末尾
                    file_size = file.tell()  # 获取文件大小
                    file.seek(0)  # 重置文件指针到开头

                    if file_size > single_file_size_limit:
                        return (
                            jsonify(
                                {
                                    "error": f"单个文件大小超过限制: {file.filename}，最大允许{settings.single_file_size_limit}MB"
                                }
                            ),
                            400,
                        )

                    # 检查总文件大小
                    total_upload_size += file_size
                    if total_upload_size > total_file_size_limit:
                        return (
                            jsonify(
                                {
                                    "error": f"总文件大小超过限制，最大允许{settings.total_file_size_limit}MB"
                                }
                            ),
                            400,
                        )

                    # 生成安全且保留中文的文件名
                    def generate_safe_filename(original_filename):
                        """
                        生成安全的文件名，保留中文等非ASCII字符，确保唯一性
                        """
                        # 分离文件名和扩展名
                        name, ext = os.path.splitext(original_filename)
                        # 生成唯一标识符
                        unique_id = uuid.uuid4().hex[:8]
                        # 使用时间戳和唯一ID确保文件名唯一性
                        timestamp = datetime.now(
                            pytz.timezone("Asia/Shanghai")
                        ).strftime("%Y%m%d%H%M%S")
                        # 保留原始文件名，仅移除路径分隔符防止目录遍历
                        safe_name = name.replace("/", "").replace("\\", "")
                        # 构建最终文件名
                        return f"{safe_name}_{timestamp}_{unique_id}{ext}"

                    # 使用自定义函数生成文件名
                    filename = generate_safe_filename(file.filename)
                    filepath = os.path.join(current_app.config["FILE_FOLDER"], filename)
                    file.save(filepath)

                    # 获取实际文件大小（比file.content_length更可靠）
                    actual_size = os.path.getsize(filepath)

                    # 记录文件信息（存储相对URL而不是本地路径）
                    files.append(
                        {
                            "name": filename,
                            "path": f"/uploads/files/{filename}",
                            "size": actual_size,
                            "type": file.content_type,
                        }
                    )

        # 更新基本信息
        application.self_score = data.get("self_score", application.self_score)
        application.status = data.get("status", application.status)
        application.final_score = data.get("final_score", application.final_score)
        application.review_comment = data.get(
            "review_comment", application.review_comment
        )
        application.reviewed_at = (
            datetime.fromisoformat(data["reviewed_at"])
            if "reviewed_at" in data and isinstance(data["reviewed_at"], str)
            else application.reviewed_at
        )
        application.reviewed_by = data.get("reviewed_by", application.reviewed_by)
        application.project_name = data.get("project_name", application.project_name)
        application.award_date = (
            datetime.fromisoformat(data["award_date"]).date()
            if "award_date" in data and isinstance(data["award_date"], str)
            else application.award_date
        )
        application.description = data.get("description", application.description)
        application.student_id = data.get("student_id", application.student_id)
        application.student_name = data.get("student_name", application.student_name)
        application.faculty_id = data.get("faculty_id", application.faculty_id)
        application.department_id = data.get("department_id", application.department_id)
        application.major_id = data.get("major_id", application.major_id)
        application.application_type = data.get(
            "application_type", application.application_type
        )
        application.rule_id = data.get("rule_id", application.rule_id)
        application.dynamic_coefficients = data.get(
            "dynamic_coefficients", application.dynamic_coefficients
        )

        # 只有当有新文件上传时才更新文件列表
        if files:
            application.files = files
        elif "files" in data:
            # 保留原有文件的size字段
            existing_files = application.files or []
            new_files = data["files"] or []

            # 创建一个字典映射文件路径到size
            file_size_map = {}
            for file in existing_files:
                if "path" in file and "size" in file:
                    file_size_map[file["path"]] = file["size"]

            # 更新新文件列表中的size字段
            updated_files = []
            for file in new_files:
                updated_file = file.copy()
                if "path" in updated_file and updated_file["path"] in file_size_map:
                    updated_file["size"] = file_size_map[updated_file["path"]]
                updated_files.append(updated_file)

            application.files = updated_files

        db.session.commit()

        return jsonify({"message": "申请更新成功"}), 200
    except Exception as e:
        # 记录详细错误信息
        traceback_str = traceback.format_exc()
        print("更新申请时发生错误:")
        print(str(e))
        print("详细错误堆栈:")
        print(traceback_str)
        return (
            jsonify(
                {
                    "error": "服务器内部错误",
                    "details": str(e),
                    "traceback": traceback_str,
                }
            ),
            500,
        )


# 审核申请
@application_bp.route("/applications/<int:id>/review", methods=["POST"])
def review_application(id):
    application = Application.query.get_or_404(id)
    data = request.get_json()

    application.status = data["status"]

    # 获取教师输入的分数，如果有的话优先使用
    teacher_final_score = data.get("finalScore")

    # 如果教师输入了分数，先验证分数范围，确保在0-100之间
    if teacher_final_score is not None:
        # 确保分数在0-100之间
        teacher_final_score = max(0, min(100, teacher_final_score))
        application.final_score = teacher_final_score
    elif (
        application.application_type == "academic" and application.status == "approved"
    ):
        # 教师未输入分数，自动计算最终分数（仅适用于学术专长申请）
        matched_rule = None

        # 1. 首先检查学生是否已经选择了规则
        if application.rule_id:
            matched_rule = Rule.query.get(application.rule_id)

        # 2. 如果学生没有选择规则，先检查是否有匹配的特殊规则
        if not matched_rule:
            # 查询所有符合条件的规则
            rule_query = Rule.query.filter_by(
                type="academic",
                sub_type=application.application_type,
                status="active",
            )

            # 根据application_type确定规则
            # 这里可以根据实际需求调整规则匹配逻辑

            matched_rule = rule_query.first()

        if matched_rule:
            # 3. 检查最大项目数量限制
            max_count_exceeded = False
            if matched_rule.max_count:
                # 统计该学生已通过的同类型项目数量（排除当前项目）
                approved_count = Application.query.filter(
                    Application.student_id == application.student_id,
                    Application.application_type == "academic",
                    Application.application_type == application.application_type,
                    Application.status == "approved",
                    Application.id != application.id,  # 排除当前正在审核的项目
                ).count()

                if approved_count >= matched_rule.max_count:
                    max_count_exceeded = True

            if max_count_exceeded:
                # 超过最大项目数量限制，不给予加分
                application.final_score = 0
            else:
                # 计算基础分数
                final_score = matched_rule.score

                # 应用动态系数（如果有）
                if application.dynamic_coefficients:
                    # 这里可以根据实际需求调整动态系数的应用逻辑
                    final_score *= application.dynamic_coefficients

                # 应用最大分数限制（如果有）
                if matched_rule.max_score:
                    final_score = min(final_score, matched_rule.max_score)

                # 设置最终分数
                application.final_score = final_score
        else:
            # 如果没有匹配的规则，设置为0分
            application.final_score = 0
    else:
        # 非学术专长申请或未通过，教师未输入分数，设置为0分
        application.final_score = 0

    application.review_comment = data.get("reviewComment")
    application.reviewed_at = datetime.now(pytz.timezone("Asia/Shanghai"))
    application.reviewed_by = data.get("reviewedBy")

    db.session.commit()

    # 更新学生的统计数据
    update_student_statistics(application.student_id)

    return jsonify({"message": "申请审核成功"}), 200


# 删除申请
@application_bp.route("/applications/<int:id>", methods=["DELETE"])
def delete_application(id):
    application = Application.query.get_or_404(id)

    # 获取学生ID，用于后续更新统计数据
    student_id = application.student_id

    # 删除相关物理文件
    if application.files:
        for file in application.files:
            try:
                # 从文件路径中提取文件名
                if "path" in file and file["path"]:
                    # 获取文件名（从URL中提取）
                    filename = os.path.basename(file["path"])
                    # 构建完整的文件路径
                    file_path = os.path.join(
                        current_app.config["FILE_FOLDER"], filename
                    )
                    # 检查文件是否存在并删除
                    if os.path.exists(file_path):
                        os.remove(file_path)
            except Exception as e:
                # 记录错误但不中断删除流程
                print(f"删除文件失败: {str(e)}")

    db.session.delete(application)
    db.session.commit()

    # 更新学生的统计数据
    update_student_statistics(student_id)

    return jsonify({"message": "申请删除成功"}), 200


# 获取待审核申请
@application_bp.route("/applications/pending", methods=["GET"])
def get_pending_applications():
    # 获取查询参数
    faculty_id = request.args.get("facultyId")
    department_id = request.args.get("departmentId")
    major_id = request.args.get("majorId")
    application_type = request.args.get("applicationType")
    student_id = request.args.get("studentId")
    student_name = request.args.get("studentName")

    # 构建查询
    query = Application.query.filter_by(status="pending")

    # 按学院筛选
    if faculty_id:
        query = query.filter_by(faculty_id=faculty_id)

    if department_id:
        query = query.filter_by(department_id=department_id)

    if major_id:
        query = query.filter_by(major_id=major_id)

    if application_type:
        query = query.filter_by(application_type=application_type)

    if student_id:
        query = query.filter_by(student_id=student_id)

    if student_name:
        query = query.filter(Application.student_name.like(f"%{student_name}%"))

    applications = query.all()
    app_list = []

    # 获取所有相关系、专业和规则信息以避免N+1查询问题
    from models import Department, Major, Rule

    department_ids = {app.department_id for app in applications}
    departments = Department.query.filter(Department.id.in_(department_ids)).all()
    department_dict = {d.id: d.name for d in departments}

    major_ids = {app.major_id for app in applications}
    majors = Major.query.filter(Major.id.in_(major_ids)).all()
    major_dict = {m.id: m.name for m in majors}

    # 批量获取规则信息
    rule_ids = {app.rule_id for app in applications if app.rule_id}
    rules = Rule.query.filter(Rule.id.in_(rule_ids)).all() if rule_ids else []

    # 获取所有规则的计算配置
    from models import RuleCalculation

    rule_calculations = (
        RuleCalculation.query.filter(RuleCalculation.rule_id.in_(rule_ids)).all()
        if rule_ids
        else []
    )
    calculation_dict = {calc.rule_id: calc for calc in rule_calculations}

    rule_dict = {
        rule.id: {
            "id": rule.id,
            "name": rule.name,
            "score": rule.score,
            "description": rule.description,
            "calculation": (
                {
                    "id": calculation_dict[rule.id].id,
                    "rule_id": calculation_dict[rule.id].rule_id,
                    "calculation_type": calculation_dict[rule.id].calculation_type,
                    "formula": calculation_dict[rule.id].formula,
                    "parameters": calculation_dict[rule.id].parameters,
                    "max_score": calculation_dict[rule.id].max_score,
                }
                if rule.id in calculation_dict
                else None
            ),
        }
        for rule in rules
    }

    for app in applications:
        # 转换文件路径格式
        processed_files = []
        if app.files:
            for file in app.files:
                processed_file = file.copy() if isinstance(file, dict) else file
                if isinstance(processed_file, dict) and "path" in processed_file:
                    # 如果是本地绝对路径，转换为相对URL
                    if os.path.isabs(processed_file["path"]):
                        # 从绝对路径中提取文件名和子文件夹
                        filename = os.path.basename(processed_file["path"])
                        # 判断文件应该属于哪个子文件夹
                        if "avatars" in processed_file["path"]:
                            processed_file["path"] = f"/uploads/avatars/{filename}"
                        else:
                            # 默认将其他文件归类到files文件夹
                            processed_file["path"] = f"/uploads/files/{filename}"
                processed_files.append(processed_file)

        app_data = {
            "id": app.id,
            "studentId": app.student_id,
            "studentName": app.student_name,
            "facultyId": app.faculty_id,
            "departmentId": app.department_id,
            "department": department_dict.get(app.department_id, "未知系"),
            "majorId": app.major_id,
            "major": major_dict.get(app.major_id, "未知专业"),
            "applicationType": app.application_type,
            "appliedAt": app.applied_at.isoformat() if app.applied_at else None,
            "selfScore": app.self_score,
            "status": app.status,
            "projectName": app.project_name,
            "awardDate": app.award_date.isoformat() if app.award_date else None,
            "description": app.description,
            "files": processed_files,
            # 规则信息
            "ruleId": app.rule_id,
            "rule": rule_dict.get(app.rule_id) if app.rule_id else None,
            # 动态系数字段
            "dynamicCoefficients": app.dynamic_coefficients,
        }
        app_list.append(app_data)

    return jsonify(app_list), 200
