# -*- coding: utf-8 -*-
"""
API路由定义文件

该文件包含健康检查相关路由，使用蓝图模式实现。
"""

from flask import Blueprint, jsonify

# 创建蓝图
main_bp = Blueprint("main", __name__)


# 根路径健康检查 - 现在会变成 /api/
@main_bp.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok", "message": "Server is running"}), 200


# 健康检查接口 - 现在会变成 /api/health
@main_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "Server is running"}), 200
