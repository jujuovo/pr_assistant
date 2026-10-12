# -*- coding: utf-8 -*-
"""
公开接口蓝图
包含无需登录即可访问的接口
"""
from flask import Blueprint, jsonify, current_app, send_from_directory
from datetime import datetime, time
from models import SystemSettings
from extensions import db
from urllib.parse import quote

# 创建公开接口蓝图
public_bp = Blueprint("public", __name__)


# 公开接口：获取系统信息
@public_bp.route("/system-info", methods=["GET"])
def get_system_info():
    """
    获取公开的系统信息，包括推免申请开放时间
    此接口无需登录权限即可访问
    """
    try:
        # 从数据库中获取系统设置
        system_settings = SystemSettings.query.first()

        # 如果数据库中没有系统设置，则使用默认值
        if system_settings:
            # 直接使用数据库中存储的完整日期时间
            if system_settings.application_start:
                start_datetime = system_settings.application_start
            else:
                start_datetime = datetime(
                    2025, 9, 1, 10, 0, 0
                )  # 默认开始时间设置为10:00

            if system_settings.application_end:
                end_datetime = system_settings.application_end
            else:
                end_datetime = datetime(
                    2025, 9, 30, 17, 0, 0
                )  # 默认结束时间设置为17:00

            system_status = (
                system_settings.system_status
                if system_settings.system_status
                else "online"
            )
        else:
            # 默认为空
            start_datetime = None
            end_datetime = None
            system_status = None

        # 构建系统信息响应
        system_info = {
            "applicationStartTime": (
                start_datetime.isoformat() if start_datetime else None
            ),
            "applicationEndTime": end_datetime.isoformat() if end_datetime else None,
            "systemName": "研究生推免系统",
            "version": "1.0.0",
            "status": (
                "正常运行"
                if system_status in ["online", "正常"]
                else ("维护中" if system_status else None)
            ),
            # 添加文件上传相关设置
            "singleFileSizeLimit": (
                system_settings.single_file_size_limit if system_settings else 10
            ),
            "totalFileSizeLimit": (
                system_settings.total_file_size_limit if system_settings else 50
            ),
            "allowedFileTypes": (
                system_settings.allowed_file_types
                if system_settings
                else ".pdf, .jpg, .jpeg, .png"
            ),
        }

        return jsonify(
            {"code": 200, "message": "获取系统信息成功", "data": system_info}
        )

    except Exception as e:
        # 记录错误日志
        print(f"获取系统信息异常: {str(e)}")
        return jsonify(
            {"code": 500, "message": f"获取系统信息失败: {str(e)}", "data": None}
        )
