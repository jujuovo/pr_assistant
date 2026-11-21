# -*- coding: utf-8 -*-
"""
应用配置文件

该文件定义了应用的配置参数，包括数据库连接、密钥配置等，
用于集中管理应用的配置信息，便于不同环境下的切换和维护。
"""

import os
from pathlib import Path
import secrets

BACKEND_ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get('APP_DATA_ROOT', str(BACKEND_ROOT)))


def data_path(name):
    return str(DATA_ROOT / name)


def local_secret():
    """Share a local session secret across Web/worker without committing it."""
    if os.environ.get('SECRET_KEY'):
        return os.environ['SECRET_KEY']
    if os.environ.get('APP_ENV') == 'production':
        raise RuntimeError('生产环境必须设置 SECRET_KEY')
    path = DATA_ROOT / 'instance' / '.session-secret'
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            output.write(secrets.token_hex(32))
    return path.read_text(encoding='utf-8').strip()


class Config:
    # 数据库配置
    # 使用URL对象构建数据库连接字符串，避免编码问题
    SQLALCHEMY_DATABASE_URI = "postgresql://localhost/gradpush"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 独立识别工作进程与 Web 使用同一数据库；测试可指向隔离 SQLite。
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", SQLALCHEMY_DATABASE_URI)
    AUTOMATION_UPLOAD_FOLDER = data_path('private-materials')
    AUTOMATION_MAX_FILES = 30
    AUTOMATION_MAX_IMAGE_BYTES = 10 * 1024 * 1024
    AUTOMATION_MAX_PIXELS = 20_000_000
    AUTOMATION_LEASE_SECONDS = 600
    AUTOMATION_MAX_ATTEMPTS = 3

    CERTIFICATE_STORAGE_FOLDER = data_path('private-certificates')
    CERTIFICATE_MAX_FILE_BYTES = 10 * 1024 * 1024
    CERTIFICATE_MAX_PIXELS = 20_000_000
    CERTIFICATE_MAX_PDF_PAGES = 4
    OCR_MATURE_EVENT_FAMILIES = ()  # Enable only after template acceptance; teacher review remains required.
    ALLOW_LEGACY_CERTIFICATE_PREVIEWS = False
    OCR_STORAGE_FOLDER = data_path('private-ocr')
    MATERIAL_STORAGE_FOLDER = data_path('private-evidence')
    MATERIAL_MAX_FILE_BYTES = 10 * 1024 * 1024
    OCR_MODEL_ROOT = os.environ.get('OCR_MODEL_ROOT', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ocr-models'))

    # 密钥配置
    SECRET_KEY = local_secret()

    # 文件上传配置
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', str(DATA_ROOT / 'uploads') if os.environ.get('APP_DATA_ROOT') else os.path.join(os.getcwd(), 'uploads'))
    AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, "avatars")
    FILE_FOLDER = os.path.join(UPLOAD_FOLDER, "files")
    GRADUATE_FILES_FOLDER = os.path.join(UPLOAD_FOLDER, "graduate-files")
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB，支持多文件上传
    
    # Session配置
    SESSION_TYPE = 'filesystem'  # 使用文件系统存储session
    SESSION_FILE_DIR = os.environ.get('SESSION_FILE_DIR', str(DATA_ROOT / 'sessions') if os.environ.get('APP_DATA_ROOT') else os.path.join(os.getcwd(), 'cache'))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_PERMANENT = False  # 不是永久session
    SESSION_USE_SIGNER = True  # 使用签名
    SESSION_KEY_PREFIX = 'gradpush:'  # session键前缀
    PERMANENT_SESSION_LIFETIME = 1800  # session有效期（秒）
