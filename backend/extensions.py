# -*- coding: utf-8 -*-
"""
扩展管理器

该文件负责初始化和管理Flask扩展，如SQLAlchemy数据库扩展，
将扩展初始化与应用主入口分离，保持代码的模块化和可维护性。
"""

import os
import sqlite3

from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from sqlalchemy import event
from sqlalchemy.engine import Engine

# 创建数据库对象，供其他模块导入
db = SQLAlchemy()

# 创建session对象，用于存储验证码等临时数据
session = Session()


def foreign_keys_enabled():
    """外键约束开关，默认开启。

    测试套件里有多处用例刻意构造孤儿数据（例如「报告坏学生时不能声称完成」），
    这类状态在开启外键后无法建立，因此 conftest 会把 SQLITE_FOREIGN_KEYS 设为 0。
    生产/本地开发环境保持默认开启，避免脏数据。
    """
    return os.environ.get("SQLITE_FOREIGN_KEYS", "1").strip().lower() not in ("0", "false", "off", "no")


@event.listens_for(Engine, "connect")
def _apply_sqlite_pragmas(dbapi_connection, connection_record):
    """SQLite 连接级开关：外键约束 + WAL + 均衡同步。

    SQLite 的两条默认行为在多人协作时都不合适：
      1. `foreign_keys` 逐个连接默认关闭，外键声明形同虚设；
      2. 默认 rollback journal 模式下，写会锁住整库，读要等待。

    Web 与 OCR worker 同时读写时，这两条会分别造成脏数据和锁等待。
    这里只在 SQLite 连接上生效，PostgreSQL 等其它方言直接返回。
    """
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(f"PRAGMA foreign_keys={'ON' if foreign_keys_enabled() else 'OFF'}")
        # 内存库不支持 WAL，执行后仍返回 memory，不影响功能
        cursor.execute("PRAGMA journal_mode=WAL")
        # WAL 下的均衡档：掉电可能丢最后一个事务，但不会损坏库
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()
