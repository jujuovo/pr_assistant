# -*- coding: utf-8 -*-
"""
数据模型文件

该文件定义了应用的数据库模型，包括用户模型(User)、申请模型(Application)和学生模型(Student)，
负责数据库表结构的设计和数据关系的定义，提供数据操作的基础。

主要模型：
- User: 用户信息模型，存储用户账号、密码、角色等信息
- Application: 申请信息模型，存储推免加分申请的相关数据
- Student: 学生信息模型，合并了学生基本信息和总评成绩
- PerformanceDetail: 合并了学术专长和综合表现详情
- Rule: 加分规则模型，存储推免加分的规则定义
- Faculty: 学院信息模型，存储学院信息
- Department: 系信息模型，存储系信息
- Major: 专业信息模型，存储专业信息
"""

from extensions import db
from datetime import datetime
import bcrypt
from sqlalchemy import event
import pytz

# 设置上海时区
shanghai_tz = pytz.timezone("Asia/Shanghai")


# 获取当前时间（上海时区）
def get_current_time():
    return datetime.now(shanghai_tz)


# 学院模型
class Faculty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)  # 学院名称
    description = db.Column(db.Text, nullable=True)  # 学院描述
    created_at = db.Column(db.DateTime, default=get_current_time)  # 创建时间
    updated_at = db.Column(
        db.DateTime, default=get_current_time, onupdate=get_current_time
    )  # 更新时间

    # 关系
    departments = db.relationship("Department", backref="faculty", lazy=True)

    def __repr__(self):
        return f"<Faculty {self.name}>"


# 系模型
class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 系名称
    faculty_id = db.Column(
        db.Integer, db.ForeignKey("faculty.id"), nullable=False
    )  # 所属学院
    description = db.Column(db.Text, nullable=True)  # 系描述
    created_at = db.Column(db.DateTime, default=get_current_time)  # 创建时间
    updated_at = db.Column(
        db.DateTime, default=get_current_time, onupdate=get_current_time
    )  # 更新时间

    # 关系
    majors = db.relationship("Major", backref="department", lazy=True)

    def __repr__(self):
        return f"<Department {self.name}>"


# 专业模型
class Major(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 专业名称
    department_id = db.Column(
        db.Integer, db.ForeignKey("department.id"), nullable=False
    )  # 所属系
    description = db.Column(db.Text, nullable=True)  # 专业描述
    created_at = db.Column(db.DateTime, default=get_current_time)  # 创建时间
    updated_at = db.Column(
        db.DateTime, default=get_current_time, onupdate=get_current_time
    )  # 更新时间

    def __repr__(self):
        return f"<Major {self.name}>"


# 用户模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # student, teacher, admin
    avatar = db.Column(db.String(200), nullable=True)
    # 使用外键关联学院、系、专业
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=True)
    major_id = db.Column(db.Integer, db.ForeignKey("major.id"), nullable=True)
    # 与Student模型建立外键关系
    student_id = db.Column(
        db.String(20), db.ForeignKey("student.student_id"), nullable=True, unique=True
    )
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    role_name = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default="active")  # active, disabled
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=get_current_time)
    updated_at = db.Column(
        db.DateTime, default=get_current_time, onupdate=get_current_time
    )

    # 与Student模型建立一对一关系
    student = db.relationship(
        "Student", backref=db.backref("user", uselist=False), foreign_keys=[student_id]
    )

    def __repr__(self):
        return f"<User {self.username}>"

    # 保存前确保学生用户的信息与Student模型同步
    def before_save(self):
        if self.role == "student" and self.student:
            # 同步学生用户的基本信息到Student模型
            self.student.student_name = self.name
            # 同步学院、系、专业信息到Student模型
            if self.faculty_id:
                self.student.faculty_id = self.faculty_id
            if self.department_id:
                self.student.department_id = self.department_id
            if self.major_id:
                self.student.major_id = self.major_id

    # 设置密码（哈希）
    def set_password(self, password):
        self.password = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    # 验证密码
    def check_password(self, password):
        return bcrypt.checkpw(password.encode("utf-8"), self.password.encode("utf-8"))


# 申请模型
class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.String(20), db.ForeignKey("student.student_id"), nullable=False
    )
    student_name = db.Column(db.String(100), nullable=False)
    # 使用外键关联学院、系和专业
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=True)
    department_id = db.Column(
        db.Integer, db.ForeignKey("department.id"), nullable=False
    )
    major_id = db.Column(db.Integer, db.ForeignKey("major.id"), nullable=False)
    application_type = db.Column(
        db.String(50), nullable=False
    )  # academic, comprehensive
    applied_at = db.Column(db.DateTime, default=get_current_time)
    self_score = db.Column(db.Float, nullable=True)
    status = db.Column(
        db.String(20), default="pending"
    )  # pending, approved, rejected, draft
    project_name = db.Column(db.String(200), nullable=False)
    award_date = db.Column(db.Date, nullable=True)
    description = db.Column(db.Text, nullable=True)
    files = db.Column(db.JSON, nullable=True)  # 存储文件信息的JSON数组
    dynamic_coefficients = db.Column(db.JSON, nullable=True)  # 存储动态系数数据的JSON对象

    # 审核相关字段
    final_score = db.Column(db.Float, nullable=True)  # 最终核定分数
    review_comment = db.Column(db.Text, nullable=True)  # 审核意见
    reviewed_at = db.Column(db.DateTime, nullable=True)  # 审核时间
    reviewed_by = db.Column(db.String(100), nullable=True)  # 审核人

    # 规则关联
    rule_id = db.Column(db.Integer, db.ForeignKey("rule.id"), nullable=True)

    # 关系定义
    faculty = db.relationship("Faculty", backref=db.backref("applications", lazy=True))
    department = db.relationship(
        "Department", backref=db.backref("applications", lazy=True)
    )
    major = db.relationship("Major", backref=db.backref("applications", lazy=True))

    created_at = db.Column(db.DateTime, default=get_current_time)
    updated_at = db.Column(
        db.DateTime, default=get_current_time, onupdate=get_current_time
    )

    def __repr__(self):
        return f"<Application {self.id}>"


# 学生总评模型
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False)  # 学号
    student_name = db.Column(db.String(100), nullable=False)  # 姓名
    gender = db.Column(db.String(10), nullable=True)  # 性别
    # 外键关联学院、系和专业
    faculty_id = db.Column(
        db.Integer, db.ForeignKey("faculty.id"), nullable=True
    )  # 学院ID
    department_id = db.Column(
        db.Integer, db.ForeignKey("department.id"), nullable=False
    )  # 系ID
    major_id = db.Column(
        db.Integer, db.ForeignKey("major.id"), nullable=False
    )  # 专业ID
    # 关系
    faculty = db.relationship("Faculty", backref=db.backref("students", lazy=True))
    department = db.relationship(
        "Department", backref=db.backref("students", lazy=True)
    )
    major = db.relationship("Major", backref=db.backref("students", lazy=True))
    cet4_score = db.Column(db.Integer, nullable=True)  # CET4成绩
    cet6_score = db.Column(db.Integer, nullable=True)  # CET6成绩

    # 学业综合成绩
    gpa = db.Column(db.Float, nullable=True)  # 推免绩点(满分4分)
    academic_score = db.Column(db.Float, nullable=True)  # 换算后的学业成绩(满分100分)

    # 学术专长成绩（占总分12%）
    academic_specialty_total = db.Column(db.Float, nullable=True)  # 学院核定总分

    # 综合表现加分（占总分8%）
    comprehensive_performance_total = db.Column(db.Float, nullable=True)  # 学院核定总分

    # 总分与排名
    comprehensive_score = db.Column(db.Float, nullable=True)  # 综合成绩
    major_ranking = db.Column(db.Integer, nullable=True)  # 专业成绩排名
    total_students = db.Column(db.Integer, nullable=True)  # 排名人数

    created_at = db.Column(db.DateTime, default=get_current_time)
    updated_at = db.Column(
        db.DateTime, default=get_current_time, onupdate=get_current_time
    )

    def __repr__(self):
        return f"<Student {self.student_name} ({self.student_id})>"

    # 保存前确保学生信息与User模型同步
    def before_save(self):
        if self.user:
            # 同步学生的基本信息到User模型
            self.user.name = self.student_name
            # 同步学院、系、专业信息到User模型
            if self.faculty_id:
                self.user.faculty_id = self.faculty_id
            if self.department_id:
                self.user.department_id = self.department_id
            if self.major_id:
                self.user.major_id = self.major_id


# 添加事件监听器，确保在保存前调用同步方法
@event.listens_for(User, "before_insert")
@event.listens_for(User, "before_update")
def call_before_save_user(mapper, connection, target):
    if hasattr(target, "before_save"):
        target.before_save()


@event.listens_for(Student, "before_insert")
@event.listens_for(Student, "before_update")
def call_before_save_student(mapper, connection, target):
    if hasattr(target, "before_save"):
        target.before_save()


# 加分规则模型
class Rule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)  # 规则名称
    type = db.Column(
        db.String(50), nullable=False
    )  # 规则类型: academic(学术专长), comprehensive(综合表现)
    sub_type = db.Column(
        db.String(50), nullable=True
    )  # 子类型: research(科研成果), competition(学业竞赛), innovation(创新创业训练), etc.
    research_type = db.Column(
        db.String(50), nullable=True
    )  # 科研成果类型: thesis(学术论文), patent(发明专利)
    score = db.Column(db.Float, nullable=False)  # 基础分值
    max_score = db.Column(
        db.Float, nullable=True
    )  # 最大分数限制（如创新创业训练最多加2分）
    max_count = db.Column(
        db.Integer, nullable=True
    )  # 最大项目数量限制（如学业竞赛不超过3项）
    status = db.Column(db.String(20), default="active")  # 状态: active, disabled
    description = db.Column(db.Text, nullable=True)  # 规则描述

    # 学院级规则支持字段
    faculty_id = db.Column(
        db.Integer, db.ForeignKey("faculty.id"), nullable=True
    )  # 学院ID，支持学院级规则

    # 计算规则字段
    calculation_formula = db.Column(
        db.JSON, nullable=True
    )  # 动态分值计算公式，支持多种计算类型

    # 关系定义
    faculty = db.relationship("Faculty", backref=db.backref("rules", lazy=True))

    created_at = db.Column(db.DateTime, default=get_current_time)  # 创建时间
    updated_at = db.Column(
        db.DateTime, default=get_current_time, onupdate=get_current_time
    )  # 更新时间

    def __repr__(self):
        return f"<Rule {self.name}>"


# 规则计算模型
class RuleCalculation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(
        db.Integer, db.ForeignKey("rule.id"), nullable=False
    )  # 关联的规则ID
    calculation_type = db.Column(
        db.String(50), default="fixed"
    )  # 计算类型: fixed(固定分值), ratio(比例计算), formula(公式计算)
    formula = db.Column(
        db.String(200), nullable=True
    )  # 计算公式字符串，如"base_score * level_factor * grade_factor"
    parameters = db.Column(
        db.JSON, nullable=True
    )  # 计算参数，存储为JSON格式，包含各种系数和配置
    max_score = db.Column(db.Float, nullable=True)  # 最大分值限制
    precision = db.Column(db.Integer, default=2)  # 计算结果的小数位数
    status = db.Column(db.String(20), default="active")  # 状态: active, disabled
    created_at = db.Column(db.DateTime, default=get_current_time)  # 创建时间
    updated_at = db.Column(
        db.DateTime, default=get_current_time, onupdate=get_current_time
    )  # 更新时间

    # 关系定义 - 设置为一对一关系
    rule = db.relationship(
        "Rule",
        backref=db.backref("calculation", uselist=False, lazy=True, cascade="all, delete-orphan"),
    )

    def __repr__(self):
        return f"<RuleCalculation {self.calculation_type} {self.formula}>"


# 学院成绩比例设置模型
class FacultyScoreSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(
        db.Integer, db.ForeignKey("faculty.id"), nullable=False, unique=True
    )  # 学院ID，一对一关系

    # 综合成绩比例设置
    academic_score_weight = db.Column(db.Float, default=80.0)  # 学业成绩比例（%）
    specialty_max_score = db.Column(db.Float, default=15.0)  # 学术专长分数上限
    performance_max_score = db.Column(db.Float, default=5.0)  # 综合表现分数上限

    # 关系
    faculty = db.relationship(
        "Faculty", backref=db.backref("score_settings", uselist=False)
    )

    created_at = db.Column(db.DateTime, default=get_current_time)
    updated_at = db.Column(
        db.DateTime, default=get_current_time, onupdate=get_current_time
    )

    def __repr__(self):
        return f"<FacultyScoreSettings faculty_id={self.faculty_id}>"


# 验证码模型
class Captcha(db.Model):
    __tablename__ = 'captcha'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(36), unique=True, nullable=False, index=True)  # UUID格式的token
    text = db.Column(db.String(10), nullable=False)  # 验证码文本
    user_identifier = db.Column(db.String(100), nullable=False, index=True)  # 用户标识符（IP+User-Agent的哈希值）
    created_at = db.Column(db.DateTime, default=get_current_time)  # 创建时间
    expired_at = db.Column(db.DateTime, nullable=False)  # 过期时间
    
    def __repr__(self):
        return f"<Captcha {self.token[:8]}>"


# 系统设置模型
class SystemSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # 学术年度设置
    academic_year = db.Column(db.String(10), default="2023")
    application_start = db.Column(db.DateTime, nullable=True)
    application_end = db.Column(db.DateTime, nullable=True)

    # 文件存储设置
    single_file_size_limit = db.Column(db.Integer, default=10)  # 单文件大小限制（MB）
    total_file_size_limit = db.Column(db.Integer, default=50)  # 总文件大小限制（MB）
    avatar_file_size_limit = db.Column(db.Integer, default=2)  # 头像文件大小限制（MB）
    allowed_file_types = db.Column(db.String(200), default=".pdf, .jpg, .jpeg, .png")

    # 系统维护信息
    system_status = db.Column(db.String(20), default="online")  # online, maintenance
    last_backup = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=get_current_time)
    updated_at = db.Column(
        db.DateTime, default=get_current_time, onupdate=get_current_time
    )

    def __repr__(self):
        return f"<SystemSettings id={self.id}>"


# 推免相关文件模型
class GraduateFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)  # 文件名
    filepath = db.Column(db.String(255), nullable=False)  # 文件路径
    file_size = db.Column(db.Integer, nullable=False)  # 文件大小（字节）
    file_type = db.Column(db.String(100), nullable=False)  # 文件类型
    upload_time = db.Column(db.DateTime, default=get_current_time)  # 上传时间
    uploader = db.Column(db.String(100), nullable=True)  # 上传者
    description = db.Column(db.Text, nullable=True)  # 文件描述
    category = db.Column(
        db.String(100), default="graduate"
    )  # 文件类别，默认是graduate（推免相关）
    faculty_id = db.Column(
        db.Integer, db.ForeignKey("faculty.id"), nullable=True
    )  # 所属学院

    # 关系
    faculty = db.relationship(
        "Faculty", backref=db.backref("graduate_files", lazy=True)
    )

    created_at = db.Column(db.DateTime, default=get_current_time)
    updated_at = db.Column(
        db.DateTime, default=get_current_time, onupdate=get_current_time
    )

    def __repr__(self):
        return f"<GraduateFile {self.filename}>"
