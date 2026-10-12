# -*- coding: utf-8 -*-
"""
认证相关蓝图

该文件负责处理用户认证相关的API端点，包括：
- 登录
- 注册
- 密码重置
- 验证码
- 学院、系、专业列表获取（用于注册选择）
- 用户登出、登录状态检查
"""

from flask import Blueprint, request, jsonify, make_response, session
from models import User, Faculty, Department, Major, Student, Captcha
from datetime import datetime, timedelta
import pytz
from extensions import db
from utils.captcha import generate_captcha
import base64
from io import BytesIO
import uuid
import hashlib

# 引入组织信息管理模块
from .organization_bp import (
    get_all_faculties,
    get_departments_by_faculty_id,
    get_all_majors,
    get_majors_by_department_id,
    get_majors_by_faculty_id,
)


# 清理过期验证码的函数
def cleanup_expired_captchas():
    current_time = datetime.now(pytz.timezone("Asia/Shanghai"))
    # 从数据库中删除所有过期的验证码
    expired_count = Captcha.query.filter(Captcha.expired_at < current_time).delete()
    db.session.commit()
    if expired_count:
        print(f"清理了{expired_count}个过期验证码")


# 验证码验证函数
def validate_captcha(captcha_input, captcha_token):
    """
    验证验证码是否有效

    Args:
        captcha_input: 用户输入的验证码
        captcha_token: 验证码对应的token

    Returns:
        tuple: (是否验证成功, 错误消息)
    """
    # 验证验证码
    print(f"验证验证码: 输入={captcha_input.lower()}, token={captcha_token}")

    # 从数据库中获取验证码
    captcha = Captcha.query.filter_by(token=captcha_token).first()
    
    # 检查验证码是否存在
    if not captcha:
        print("验证码验证失败：未找到对应的验证码")
        return False, "验证码不存在，请刷新页面获取验证码"

    # 检查验证码是否过期
    current_time = datetime.now(pytz.timezone("Asia/Shanghai"))
    # 确保比较的是同类型的datetime对象（带时区的）
    # 如果expired_at不带时区，将其转换为带上海时区的datetime
    if captcha.expired_at.tzinfo is None:
        captcha.expired_at = pytz.timezone("Asia/Shanghai").localize(captcha.expired_at)
    if current_time > captcha.expired_at:
        print("验证码已过期")
        # 清除过期的验证码
        db.session.delete(captcha)
        db.session.commit()
        return False, "验证码已过期，请刷新页面获取新验证码"

    # 验证验证码内容
    if captcha_input.lower() != captcha.text:
        print(f"验证码不匹配：输入={captcha_input.lower()}, 存储={captcha.text}")
        return False, "验证码错误"

    # 验证成功后删除验证码
    db.session.delete(captcha)
    db.session.commit()

    print("验证码验证成功")
    return True, None


# 创建蓝图
auth_bp = Blueprint("auth", __name__, url_prefix="/api")


# 验证码生成接口
@auth_bp.route("/generate-captcha", methods=["GET"])
def get_captcha():
    try:
        # 先清理过期的验证码
        cleanup_expired_captchas()
        
        # 生成用户标识符（IP地址 + User-Agent的哈希值）
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        # 创建用户标识符（哈希处理以保护隐私）
        user_identifier = hashlib.sha256((ip_address + user_agent).encode()).hexdigest()[:32]
        
        # 删除同一用户的旧验证码
        current_time = datetime.now(pytz.timezone("Asia/Shanghai"))
        old_captchas = Captcha.query.filter(
            Captcha.user_identifier == user_identifier,
            Captcha.expired_at > current_time
        ).all()
        
        if old_captchas:
            for captcha in old_captchas:
                db.session.delete(captcha)
            db.session.commit()
            print(f"删除了用户{user_identifier[:8]}的{len(old_captchas)}个旧验证码")
        
        # 限制未过期验证码的数量，生产环境最多保留1000个
        # 可根据实际并发量调整此值
        MAX_ACTIVE_CAPTCHAS = 1000
        
        # 获取当前未过期的验证码数量
        active_captchas = Captcha.query.filter(Captcha.expired_at > current_time).count()
        
        # 如果未过期验证码数量超过限制，删除最旧的验证码
        if active_captchas >= MAX_ACTIVE_CAPTCHAS:
            # 查询最旧的未过期验证码
            oldest_captchas = Captcha.query.filter(Captcha.expired_at > current_time) \
                                           .order_by(Captcha.created_at.asc()) \
                                           .limit(active_captchas - (MAX_ACTIVE_CAPTCHAS - 1)) \
                                           .all()
            
            # 删除这些旧验证码
            for captcha in oldest_captchas:
                db.session.delete(captcha)
            db.session.commit()
            print(f"删除了{len(oldest_captchas)}个旧验证码，保持未过期验证码数量在合理范围内")

        # 生成验证码图片和文本
        # 注意：根据captcha.py的实现，返回值顺序是 (captcha_image, captcha_text)
        captcha_image, captcha_text = generate_captcha()

        print(f"生成验证码: {captcha_text}")

        # 生成唯一的token
        captcha_token = str(uuid.uuid4())

        # 计算过期时间（5分钟后）
        current_time = datetime.now(pytz.timezone("Asia/Shanghai"))
        expired_time = current_time + timedelta(minutes=5)

        # 创建验证码记录并存储到数据库
        captcha = Captcha(
            token=captcha_token,
            text=captcha_text.lower(),
            expired_at=expired_time,
            user_identifier=user_identifier
        )
        db.session.add(captcha)
        db.session.commit()
        print(f"验证码已存储到数据库，token: {captcha_token}, 用户标识符: {user_identifier[:8]}")

        # 将图片转换为base64字符串
        buffer = BytesIO()
        captcha_image.save(buffer, format="PNG")
        buffer.seek(0)
        img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return jsonify({"image": img_str, "token": captcha_token}), 200
    except Exception as e:
        print(f"验证码生成错误: {str(e)}")
        return jsonify({"message": "验证码生成失败"}), 500


# 登录接口 - OPTIONS请求处理
@auth_bp.route("/login", methods=["OPTIONS"])
def login_options():
    response = make_response()
    return response


# 登录接口 - POST请求处理
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    captcha_input = data.get("captcha")
    captcha_token = data.get("captchaToken")

    if not username or not password:
        return jsonify({"message": "用户名和密码不能为空"}), 400

    if not captcha_input:
        return jsonify({"message": "验证码不能为空"}), 400

    if not captcha_token:
        return jsonify({"message": "验证码token不能为空"}), 400

    # 使用通用验证码验证函数
    captcha_valid, error_message = validate_captcha(captcha_input, captcha_token)
    if not captcha_valid:
        return jsonify({"message": error_message}), 400

    print("验证码验证成功")

    # 查找用户
    user = User.query.filter_by(username=username).first()

    if not user:
        return jsonify({"message": "用户不存在"}), 401

    if user.status == "disabled":
        return jsonify({"message": "账户已被禁用"}), 401

    # 验证密码
    if not user.check_password(password):
        return jsonify({"message": "密码错误"}), 401

    # 验证码已在验证成功后删除

    # 更新最后登录时间
    user.last_login = datetime.now(pytz.timezone("Asia/Shanghai"))
    db.session.commit()

    # 设置会话变量
    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role
    session["logged_in"] = True
    print(f"已设置会话信息: 用户ID={user.id}, 用户名={user.username}")

    # 获取学院、系和专业名称

    # 安全获取关联对象的名称
    faculty = Faculty.query.get(user.faculty_id) if user.faculty_id else None
    faculty_name = faculty.name if faculty else ""

    department = (
        Department.query.get(user.department_id) if user.department_id else None
    )
    department_name = department.name if department else ""

    major = Major.query.get(user.major_id) if user.major_id else None
    major_name = major.name if major else ""

    # 返回用户信息（不包含密码）
    user_data = {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "role": user.role,
        "avatar": user.avatar,
        "faculty": faculty_name,
        "facultyId": user.faculty_id,
        "department": department_name,
        "departmentId": user.department_id,
        "major": major_name,
        "majorId": user.major_id,
        "studentId": user.student_id,
        "email": user.email,
        "phone": user.phone,
        "roleName": user.role_name,
        "lastLogin": user.last_login.isoformat() if user.last_login else None,
    }

    # 返回用户信息（不包含密码）
    return (
        jsonify(
            {"user": user_data, "message": "登录成功", "session_id": session.get("_id")}
        ),
        200,
    )


# 注册接口
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()

    # 基本数据验证
    if not data:
        return jsonify({"message": "请求数据不能为空"}), 400

    # 验证码验证
    captcha_input = data.get("captcha")
    captcha_token = data.get("captchaToken")

    if not captcha_input:
        return jsonify({"message": "验证码不能为空"}), 400

    if not captcha_token:
        return jsonify({"message": "验证码token不能为空"}), 400

    # 使用通用验证码验证函数
    captcha_valid, error_message = validate_captcha(captcha_input, captcha_token)
    if not captcha_valid:
        return jsonify({"message": error_message}), 400

    print("验证码验证成功")

    required_fields = ["username", "name", "role", "password"]
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"message": f"{field}是必填字段"}), 400

    # 检查用户名是否已存在
    existing_user = User.query.filter_by(username=data["username"]).first()
    if existing_user:
        return jsonify({"message": "用户名已存在"}), 400

    # 验证用户名和姓名长度
    if len(data["username"]) < 5 or len(data["username"]) > 20:
        return jsonify({"message": "用户名长度必须在5-20个字符之间"}), 400
    
    if len(data["name"]) < 2 or len(data["name"]) > 20:
        return jsonify({"message": "姓名长度必须在2-20个字符之间"}), 400

    # 获取关联ID并将空字符串转换为None
    faculty_id = data.get("facultyId") or None
    department_id = data.get("departmentId") or None
    major_id = data.get("majorId") or None

    # 学生角色验证
    if data["role"] == "student":
        # 验证学生必填的关联字段
        if not faculty_id or not department_id or not major_id:
            return jsonify({"message": "学生注册必须选择学院、系和专业"}), 400

        # 验证关联ID是否存在
        faculty = Faculty.query.get(faculty_id)
        department = Department.query.get(department_id)
        major = Major.query.get(major_id)

        if not faculty:
            return jsonify({"message": "学院不存在"}), 400
        if not department:
            return jsonify({"message": "系不存在"}), 400
        if not major:
            return jsonify({"message": "专业不存在"}), 400

    try:
        # 学生角色需要先处理Student记录
        student_id = None
        if data["role"] == "student":
            # 检查是否已存在对应的Student记录
            existing_student = Student.query.filter_by(
                student_id=data["username"]
            ).first()
            if not existing_student:
                # 如果不存在，创建新的Student记录
                new_student = Student(
                    student_id=data["username"],
                    student_name=data["name"],
                    faculty_id=faculty_id,
                    department_id=department_id,
                    major_id=major_id,
                )
                db.session.add(new_student)
                db.session.flush()  # 立即刷新以确保学生记录已创建
            student_id = data["username"]

        # 创建新用户
        new_user = User(
            username=data["username"],
            name=data["name"],
            role=data["role"],
            avatar="/images/default-avatar.jpg",  # 统一使用默认头像
            faculty_id=faculty_id,
            department_id=department_id if data["role"] == "student" else None,
            major_id=major_id if data["role"] == "student" else None,
            student_id=student_id,
            email="",  # 默认值
            phone="",  # 默认值
            role_name="审核员" if data["role"] == "teacher" else None,  # 默认值
        )

        # 设置密码（哈希）- 如果没有提供密码，使用默认密码
        new_user.set_password(data.get("password", "123456"))

        db.session.add(new_user)

        # 提交事务
        db.session.commit()

        return jsonify({"message": "注册成功"}), 201
    except Exception as e:
        # 发生异常时回滚事务
        db.session.rollback()
        return jsonify({"message": f"注册失败: {str(e)}"}), 500


# 密码重置接口
@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()

    # 验证码验证
    captcha_input = data.get("captcha")
    captcha_token = data.get("captchaToken")

    if not captcha_input:
        return jsonify({"message": "验证码不能为空"}), 400

    if not captcha_token:
        return jsonify({"message": "验证码token不能为空"}), 400

    # 使用通用验证码验证函数
    captcha_valid, error_message = validate_captcha(captcha_input, captcha_token)
    if not captcha_valid:
        return jsonify({"message": error_message}), 400

    print("验证码验证成功")

    username = data.get("username")
    new_password = data.get("newPassword")

    # 查找用户
    user = User.query.filter_by(username=username).first()

    if not user:
        return jsonify({"message": "用户不存在"}), 404

    # 设置新密码
    user.set_password(new_password)

    db.session.commit()

    return jsonify({"message": "密码重置成功"}), 200


# 获取所有学院（用于注册选择）
@auth_bp.route("/faculties", methods=["GET"])
def get_faculties():
    # 使用通用函数获取学院列表
    faculties = get_all_faculties(detailed=False)
    return jsonify({"faculties": faculties}), 200


# 根据学院ID获取系列表（用于注册选择）
@auth_bp.route("/departments/<int:faculty_id>", methods=["GET"])
def get_departments_by_faculty(faculty_id):
    # 使用通用函数根据学院ID获取系列表
    departments = get_departments_by_faculty_id(faculty_id, detailed=False)
    return jsonify({"departments": departments}), 200


# 获取所有专业列表
@auth_bp.route("/majors", methods=["GET"])
def get_all_majors_api():
    # 使用通用函数获取所有专业列表
    majors = get_all_majors(detailed=False)
    return jsonify({"majors": majors}), 200


# 根据系ID获取专业列表（用于注册选择）
@auth_bp.route("/majors/<int:department_id>", methods=["GET"])
def get_majors_by_department(department_id):
    # 使用通用函数根据系ID获取专业列表
    majors = get_majors_by_department_id(department_id, detailed=False)
    return jsonify({"majors": majors}), 200


@auth_bp.route("/majors/faculty/<int:faculty_id>", methods=["GET"])
def get_majors_by_faculty(faculty_id):
    """根据学院ID获取专业列表"""
    try:
        # 调用organization_bp中的通用函数
        majors = get_majors_by_faculty_id(faculty_id)
        return jsonify({"success": True, "majors": majors}), 200
    except Exception as e:
        print(f"根据学院获取专业列表时出错: {str(e)}")
        return jsonify({"success": False, "message": "获取专业列表失败"}), 500


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """用户登出功能"""
    try:
        # 检查用户是否已登录
        if "logged_in" not in session:
            return jsonify({"success": True, "message": "您尚未登录"}), 200

        # 获取用户名用于日志记录
        username = session.get("username", "未知用户")
        print(f"用户{username}登出系统")

        # 清除所有会话变量
        session.clear()

        return jsonify({"success": True, "message": "登出成功"}), 200
    except Exception as e:
        print(f"用户登出时出错: {str(e)}")
        return jsonify({"success": False, "message": "登出失败"}), 500


@auth_bp.route("/session-check", methods=["GET"])
def session_check():
    """检查用户会话是否有效"""
    try:
        if "logged_in" in session and session["logged_in"]:
            return (
                jsonify(
                    {
                        "success": True,
                        "logged_in": True,
                        "user": {
                            "id": session.get("user_id"),
                            "username": session.get("username"),
                            "user_type": session.get("user_type")
                            or session.get("role"),
                        },
                    }
                ),
                200,
            )
        else:
            return jsonify({"success": True, "logged_in": False}), 200
    except Exception as e:
        print(f"会话检查时出错: {str(e)}")
        return jsonify({"success": False, "message": "会话检查失败"}), 500
