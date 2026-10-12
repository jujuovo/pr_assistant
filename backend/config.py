# -*- coding: utf-8 -*-
"""
应用配置文件

该文件定义了应用的配置参数，包括数据库连接、密钥配置等，
用于集中管理应用的配置信息，便于不同环境下的切换和维护。
"""

import os
from sqlalchemy.engine.url import URL


class Config:
    # 数据库配置
    # 使用URL对象构建数据库连接字符串，避免编码问题
    SQLALCHEMY_DATABASE_URI = "postgresql://postgres:123456@localhost:5432/gradpush" # 本地数据库
    # SQLALCHEMY_DATABASE_URI = "postgresql://gradpush:0701284612yekYEK@localhost:5432/gradpush" # 服务器数据库
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 密钥配置
    SECRET_KEY = os.environ.get("SECRET_KEY") or "0701284612yekYEK"

    # 文件上传配置
    UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
    AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, "avatars")
    FILE_FOLDER = os.path.join(UPLOAD_FOLDER, "files")
    GRADUATE_FILES_FOLDER = os.path.join(UPLOAD_FOLDER, "graduate-files")
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB，支持多文件上传
    
    # Session配置
    SESSION_TYPE = 'filesystem'  # 使用文件系统存储session
    SESSION_FILE_DIR = os.path.join(os.getcwd(), 'cache')  # session文件存储路径
    SESSION_PERMANENT = False  # 不是永久session
    SESSION_USE_SIGNER = True  # 使用签名
    SESSION_KEY_PREFIX = 'gradpush:'  # session键前缀
    PERMANENT_SESSION_LIFETIME = 1800  # session有效期（秒）
