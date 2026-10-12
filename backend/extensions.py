# -*- coding: utf-8 -*-
"""
扩展管理器

该文件负责初始化和管理Flask扩展，如SQLAlchemy数据库扩展，
将扩展初始化与应用主入口分离，保持代码的模块化和可维护性。
"""

from flask_sqlalchemy import SQLAlchemy
from flask_session import Session

# 创建数据库对象，供其他模块导入
db = SQLAlchemy()

# 创建session对象，用于存储验证码等临时数据
session = Session()
