# -*- coding: utf-8 -*-
"""
Flask应用主入口文件

该文件负责初始化Flask应用，配置扩展，注册路由和模型，
是整个后端应用的启动点和核心配置文件。
"""

from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
from flask_migrate import Migrate
import os
import logging
from logging.handlers import RotatingFileHandler
from werkzeug.utils import safe_join
from urllib.parse import quote
from extensions import db, session
import datetime
import pytz

# 创建应用实例
app = Flask(__name__)

# 配置CORS，支持跨域请求
CORS(
    app,
    origins="*",
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)

# 加载配置
app.config.from_object("config.Config")

# 配置JSON编码
app.config["JSON_AS_ASCII"] = False  # 支持中文输出
app.config["JSONIFY_MIMETYPE"] = "application/json; charset=utf-8"  # 设置响应头 charset

# 配置日志
LOG_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOG_FOLDER, exist_ok=True)

# 设置日志格式
log_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] [%(module)s:%(funcName)s:%(lineno)d] - %(message)s'
)

# 配置文件日志
file_handler = RotatingFileHandler(
    os.path.join(LOG_FOLDER, 'app.log'),
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding='utf-8'  # 设置文件编码为UTF-8，解决中文乱码问题
)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

# 配置控制台日志
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.DEBUG)

# 添加日志处理器
app.logger.addHandler(file_handler)
app.logger.addHandler(console_handler)
app.logger.setLevel(logging.DEBUG)

# 记录应用启动信息
app.logger.info("应用启动，日志系统已配置")

# 初始化数据库
db.init_app(app)
migrate = Migrate(app, db)

# 初始化session
session.init_app(app)

# 先创建数据库对象，再导入模型
from models import User, Application, Rule
import automation_models  # 注册新增材料、任务、去重、政策及审计表

# 导入并注册蓝图
from blueprints.auth_bp import auth_bp
from blueprints.user_bp import user_bp
from blueprints.application_bp import application_bp
from blueprints.rule_bp import rule_bp
from blueprints.admin_bp import admin_bp
from blueprints.public_bp import public_bp
from blueprints.organization_bp import organization_bp
from blueprints.score_bp import score_bp
from blueprints.system_bp import system_bp
from routes import main_bp
from blueprints.automation_bp import automation_bp


# 配置推免文件的静态服务
@app.route("/uploads/graduate-files/<path:filename>")
def uploaded_graduate_file(filename):
    print(f"===== 下载推免文件 =====")
    print(f"请求的文件名: {filename}")

    from models import GraduateFile

    # 先打印配置信息
    print(f"GRADUATE_FILES_FOLDER配置: {app.config['GRADUATE_FILES_FOLDER']}")

    # 检查文件是否存在
    file_path = os.path.join(app.config["GRADUATE_FILES_FOLDER"], filename)
    print(f"检查文件是否存在: {file_path}")
    print(f"文件是否存在: {os.path.exists(file_path)}")

    if not os.path.exists(file_path):
        return jsonify({"error": "文件不存在"}), 404

    # 尝试发送文件
    try:
        # 使用传入的filename作为文件系统中的文件名
        response = send_from_directory(app.config["GRADUATE_FILES_FOLDER"], filename)

        # 尝试从数据库获取原始文件名用于下载
        # 优化查询逻辑，使用更可靠的方式匹配文件名
        graduate_file = GraduateFile.query.filter(
            GraduateFile.filepath.contains(filename)
        ).first()

        # 如果第一种方式失败，尝试更精确的匹配方式
        if not graduate_file:
            # 构建一个更精确的查询条件，确保只匹配完整的文件名部分
            from sqlalchemy import or_

            graduate_file = GraduateFile.query.filter(
                or_(
                    GraduateFile.filepath.endswith(
                        f"\\{filename}"
                    ),  # Windows路径分隔符
                    GraduateFile.filepath.endswith(f"/{filename}"),  # Linux路径分隔符
                    GraduateFile.filepath == filename,  # 直接匹配
                )
            ).first()
        # 直接使用send_from_directory的as_attachment参数和download_name参数
        # 这样可以确保使用原始文件名进行下载
        download_filename = filename  # 默认使用传入的文件名

        if graduate_file:
            download_filename = graduate_file.filename  # 使用原始文件名
            print(f"找到原始文件名: {download_filename}")
        else:
            print(f"未找到数据库记录，使用默认文件名: {download_filename}")

        # 重新构建响应，确保使用正确的下载文件名
        response = send_from_directory(
            app.config["GRADUATE_FILES_FOLDER"],
            filename,
            as_attachment=True,
            download_name=download_filename,
        )

        # 保持正确的Content-Type
        if filename.lower().endswith(".pdf"):
            response.headers["Content-Type"] = "application/pdf"
        elif filename.lower().endswith(".txt"):
            response.headers["Content-Type"] = "text/plain; charset=utf-8"
        elif filename.lower().endswith(".doc"):
            response.headers["Content-Type"] = "application/msword"
        elif filename.lower().endswith(".docx"):
            response.headers["Content-Type"] = (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        elif filename.lower().endswith(".xls"):
            response.headers["Content-Type"] = "application/vnd.ms-excel"
        elif filename.lower().endswith(".xlsx"):
            response.headers["Content-Type"] = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        elif filename.lower().endswith(".ppt"):
            response.headers["Content-Type"] = "application/vnd.ms-powerpoint"
        elif filename.lower().endswith(".pptx"):
            response.headers["Content-Type"] = (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )

        return response
    except Exception as e:
        print(f"发送文件时出错: {str(e)}")
        return jsonify({"error": "文件下载失败"}), 500


# 配置静态文件服务
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    response = send_from_directory(app.config["UPLOAD_FOLDER"], filename)
    # 使用安全的方式处理中文文件名
    response.headers["Content-Disposition"] = (
        f"attachment; filename*=UTF-8" "={quote(filename)}"
    )
    return response


# 配置头像文件的静态服务
@app.route("/uploads/avatars/<path:filename>")
def uploaded_avatar(filename):
    response = send_from_directory(app.config["AVATAR_FOLDER"], filename)
    # 头像图片直接显示在浏览器中
    response.headers["Content-Disposition"] = (
        f"inline; filename*=UTF-8" "={quote(filename)}"
    )
    return response


# 配置普通文件的静态服务
@app.route("/uploads/files/<path:filename>")
def uploaded_app_file(filename):
    # 检查文件是否是图片或PDF
    is_image = filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
    is_pdf = filename.lower().endswith(".pdf")
    response = send_from_directory(app.config["FILE_FOLDER"], filename)

    if is_image or is_pdf:
        # 图片和PDF文件设置为内联显示
        response.headers["Content-Disposition"] = (
            f"inline; filename*=UTF-8" "={quote(filename)}"
        )
        # 根据文件类型设置正确的Content-Type
        if is_image:
            # 根据文件扩展名设置对应的图片Content-Type
            if filename.lower().endswith('.png'):
                response.headers["Content-Type"] = "image/png"
            elif filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
                response.headers["Content-Type"] = "image/jpeg"
            elif filename.lower().endswith('.gif'):
                response.headers["Content-Type"] = "image/gif"
            elif filename.lower().endswith('.webp'):
                response.headers["Content-Type"] = "image/webp"
            else:
                # 默认图片类型
                response.headers["Content-Type"] = "image/jpeg"
        elif is_pdf:
            response.headers["Content-Type"] = "application/pdf"
    else:
        # 其他文件设置为附件下载
        response.headers["Content-Disposition"] = (
            f"attachment; filename*=UTF-8" "={quote(filename)}"
        )

    return response


# 注册蓝图
app.register_blueprint(public_bp, url_prefix='/api/public')  # 公开接口蓝图，无需认证
app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(application_bp)  # application_bp 已经在定义时设置了 url_prefix='/api'
app.register_blueprint(rule_bp, url_prefix='/api')
app.register_blueprint(admin_bp)
app.register_blueprint(score_bp)  # score_bp 已经在定义时设置了 url_prefix='/api'
app.register_blueprint(organization_bp)  # organization_bp 已经在定义时设置了 url_prefix='/api/organization'
app.register_blueprint(system_bp)  # system_bp 已经在定义时设置了 url_prefix='/api/system'
app.register_blueprint(main_bp, url_prefix='/api')
app.register_blueprint(automation_bp)

# 根路径路由，解决直接访问/返回404的问题
@app.route("/", methods=["GET"])
def root_index():
    return jsonify({"status": "ok", "message": "Server is running", "api_base_url": "/api"}), 200

if __name__ == "__main__":
    app.run(debug=False, port=5001, use_reloader=False)
