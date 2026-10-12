# -*- coding: utf-8 -*-
"""
系统维护蓝图

该文件负责处理系统维护相关的API端点，包括：
- 数据库备份
- 系统日志查看
- 缓存清理
"""

import os
import sys
import shutil
from flask import (
    Blueprint,
    request,
    jsonify,
    send_from_directory,
    current_app,
    send_file,
)
from datetime import datetime
from extensions import db
from models import SystemSettings
from psycopg2 import connect, OperationalError
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extensions import cursor

# 导入数据库备份模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_backup import backup_database_python, restore_database_python, restore_uploads


# 获取数据库连接
def get_db_connection():
    """
    获取数据库连接
    """
    from config import Config
    from urllib.parse import urlparse

    try:
        # 从SQLALCHEMY_DATABASE_URI解析数据库配置
        db_url = urlparse(Config.SQLALCHEMY_DATABASE_URI)
        conn = connect(
            dbname=db_url.path[1:],  # 去除开头的'/'
            user=db_url.username,
            password=db_url.password,
            host=db_url.hostname,
            port=db_url.port,
        )
        return conn
    except OperationalError as e:
        current_app.logger.error(f"无法连接到数据库: {str(e)}")
        raise e


# 创建蓝图实例
system_bp = Blueprint("system", __name__, url_prefix="/api/system")

# 设置备份文件存储路径
BACKUP_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backup"
)
LOG_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
)
CACHE_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache"
)

# 确保备份文件夹存在
os.makedirs(BACKUP_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)


# API端点：手动备份数据库
@system_bp.route("/backup", methods=["POST"])
def backup_database():
    """
    手动备份数据库
    生成包含SQL文件和uploads.zip的单个ZIP文件
    """
    try:
        import zipfile
        import io
        import tempfile
        import json

        # 记录备份开始
        current_app.logger.info("管理员开始执行数据库备份操作")

        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_app.logger.info(f"备份时间戳: {timestamp}")

        # 创建临时SQL文件
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as temp_sql:
            temp_sql_path = temp_sql.name
        current_app.logger.info(f"创建临时SQL文件: {temp_sql_path}")

        # 创建临时uploads.zip文件
        with tempfile.NamedTemporaryFile(
            suffix="_uploads.zip", delete=False
        ) as temp_zip:
            temp_zip_path = temp_zip.name
        current_app.logger.info(f"创建临时uploads.zip文件: {temp_zip_path}")

        # 执行数据库备份到临时SQL文件
        # 注意：我们直接调用备份功能，不使用会自动创建uploads.zip的函数
        conn = get_db_connection()
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        with open(temp_sql_path, "w", encoding="utf-8") as f:
            # 备份所有序列
            cursor.execute(
                """
                SELECT
                    t.table_name,
                    c.column_name,
                    pg_get_serial_sequence(t.table_name::text, c.column_name::text) AS sequence_name
                FROM
                    information_schema.tables t
                JOIN
                    information_schema.columns c ON t.table_name = c.table_name AND t.table_schema = c.table_schema
                WHERE
                    t.table_schema = 'public' AND
                    t.table_type = 'BASE TABLE' AND
                    c.column_default LIKE '%nextval%'
            """
            )
            serial_sequences = cursor.fetchall()

            sequences = set()
            for row in serial_sequences:
                sequence_name = row[2]
                if sequence_name:
                    sequences.add(sequence_name)

            # 也直接获取所有序列
            cursor.execute(
                "SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public'"
            )
            direct_sequences = cursor.fetchall()
            for seq in direct_sequences:
                sequences.add(f"public.{seq[0]}")

            if sequences:
                for seq_name in sequences:
                    f.write(f"-- 序列: {seq_name}\n")
                    # 直接查询序列值，因为序列名已经过处理是安全的
                    cursor.execute(f"SELECT last_value FROM {seq_name}")
                    seq_info = cursor.fetchone()
                    if seq_info:
                        last_value = seq_info[0]
                        # 转义序列名中的单引号
                        escaped_seq_name = seq_name.replace("'", "''")
                        f.write(
                            f"SELECT setval('{escaped_seq_name}', {last_value}, true);\n"
                        )
                f.write("\n")

            # 获取所有表
            cursor.execute(
                """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """
            )
            tables = cursor.fetchall()

            for (table_name,) in tables:
                quoted_table_name = f'public."{table_name}"'

                # 备份表结构
                f.write(f"-- 表结构: {table_name}\n")
                cursor.execute(
                    f"SELECT column_name, data_type, column_default, is_nullable FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position",
                    (table_name,),
                )
                columns = cursor.fetchall()

                f.write(f"CREATE TABLE IF NOT EXISTS {quoted_table_name} (")
                column_definitions = []

                for col_name, data_type, col_default, is_nullable in columns:
                    col_def = f'    "{col_name}" {data_type}'
                    if col_default is not None:
                        col_def += f" DEFAULT {col_default}"
                    if is_nullable == "NO":
                        col_def += " NOT NULL"
                    column_definitions.append(col_def)

                # 添加主键约束
                cursor.execute(
                    """
                    SELECT constraint_name, column_name 
                    FROM information_schema.key_column_usage 
                    WHERE table_schema = 'public' AND table_name = %s AND constraint_name LIKE '%%_pkey'
                """,
                    (table_name,),
                )
                primary_keys = cursor.fetchall()
                if primary_keys:
                    pkey_cols = [pk[1] for pk in primary_keys]
                    column_definitions.append(f'    PRIMARY KEY ("{pkey_cols[0]}")')

                f.write(",\n".join(column_definitions))
                f.write(f"\n);\n\n")

                # 备份表数据
                cursor.execute(f"SELECT * FROM {quoted_table_name}")
                rows = cursor.fetchall()

                if rows:
                    f.write(f"-- 表数据: {table_name}\n")
                    column_names = [desc[0] for desc in cursor.description]

                    for row in rows:
                        # 处理特殊字符
                        values = []
                        for value in row:
                            if value is None:
                                values.append("NULL")
                            elif isinstance(value, str):
                                # 转义单引号
                                escaped_value = value.replace("'", "''")
                                values.append(f"'{escaped_value}'")
                            elif isinstance(value, datetime):
                                values.append(f"'{value}'")
                            elif isinstance(value, list):
                                # 处理列表/数组类型，转换为JSON格式
                                json_str = json.dumps(value)
                                escaped_str = json_str.replace("'", "''")
                                values.append(f"'{escaped_str}'")
                            else:
                                values.append(str(value))

                        insert_sql = f"INSERT INTO {quoted_table_name} ({', '.join([f'\"{col}\"' for col in column_names])}) VALUES ({', '.join(values)});\n"
                        f.write(insert_sql)
                    f.write("\n")

        cursor.close()
        conn.close()

        # 备份uploads目录到临时ZIP文件
        uploads_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads"
        )
        with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            if os.path.exists(uploads_dir):
                for root, dirs, files in os.walk(uploads_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, uploads_dir)
                        zipf.write(file_path, arcname)

        # 创建最终的完整备份ZIP文件
        final_backup_filename = f"gradpush_backup_{timestamp}.zip"
        final_backup_path = os.path.join(BACKUP_FOLDER, final_backup_filename)

        with zipfile.ZipFile(final_backup_path, "w", zipfile.ZIP_DEFLATED) as final_zip:
            # 添加SQL文件到ZIP根目录
            sql_filename = os.path.basename(temp_sql_path)
            final_zip.write(
                temp_sql_path, sql_filename.replace(".sql", "_database.sql")
            )

            # 添加uploads.zip文件到ZIP根目录
            uploads_zip_filename = os.path.basename(temp_zip_path)
            final_zip.write(temp_zip_path, uploads_zip_filename)

        # 删除临时文件
        os.unlink(temp_sql_path)
        os.unlink(temp_zip_path)
        current_app.logger.info(f"删除临时文件，备份已保存到: {final_backup_filename}")

        # 更新系统设置中的最后备份时间
        settings = SystemSettings.query.first()
        if settings:
            settings.last_backup = datetime.now()
            db.session.commit()
            current_app.logger.info("系统设置中的最后备份时间已更新")

        current_app.logger.info(
            f"数据库备份成功，生成备份文件: {final_backup_filename}"
        )
        return (
            jsonify(
                {
                    "success": True,
                    "message": "数据库备份成功",
                    "backup_file": final_backup_filename,
                }
            ),
            200,
        )
    except Exception as e:
        current_app.logger.error(f"数据库备份失败: {str(e)}")
        return jsonify({"success": False, "message": f"数据库备份失败: {str(e)}"}), 500


# API端点：获取备份列表
@system_bp.route("/backups", methods=["GET"])
def get_backups():
    """
    获取备份文件列表
    只返回完整的备份ZIP文件, 不返回单独的SQL文件或uploads.zip文件
    """
    try:
        # 获取备份文件夹中的所有文件
        backup_files = []
        if os.path.exists(BACKUP_FOLDER):
            for filename in os.listdir(BACKUP_FOLDER):
                filepath = os.path.join(BACKUP_FOLDER, filename)
                if os.path.isfile(filepath):
                    # 只返回完整的备份ZIP文件（gradpush_backup_开头且以.zip结尾）
                    if filename.startswith("gradpush_backup_") and filename.endswith(
                        ".zip"
                    ):
                        # 获取文件信息
                        file_info = {
                            "name": filename,
                            "size": os.path.getsize(filepath),
                            "create_time": datetime.fromtimestamp(
                                os.path.getctime(filepath)
                            ).isoformat(),
                            "download_url": f"/api/system/backup/download/{filename}",
                        }
                        backup_files.append(file_info)

        # 按创建时间降序排序
        backup_files.sort(key=lambda x: x["create_time"], reverse=True)

        return jsonify({"success": True, "backups": backup_files}), 200
    except Exception as e:
        current_app.logger.error(f"获取备份列表失败: {str(e)}")
        return (
            jsonify({"success": False, "message": f"获取备份列表失败: {str(e)}"}),
            500,
        )


# API端点：下载备份文件
@system_bp.route("/backup/download/<filename>", methods=["GET"])
def download_backup(filename):
    """
    下载备份文件
    直接下载完整的备份ZIP文件, 该文件包含SQL和uploads.zip
    """
    try:
        # 获取文件的完整路径
        backup_path = os.path.join(BACKUP_FOLDER, filename)

        # 检查文件是否存在
        if not os.path.exists(backup_path):
            return jsonify({"success": False, "message": "备份文件不存在"}), 404

        # 直接下载文件
        return send_from_directory(BACKUP_FOLDER, filename, as_attachment=True)
    except Exception as e:
        current_app.logger.error(f"下载备份文件失败: {str(e)}")
        return (
            jsonify({"success": False, "message": f"下载备份文件失败: {str(e)}"}),
            500,
        )


# API端点：恢复数据库
@system_bp.route("/restore", methods=["POST"])
def restore_database():
    """
    从备份文件恢复数据库
    """
    try:
        import os
        
        current_app.logger.info("管理员开始执行数据库恢复操作")

        data = request.get_json()
        filename = data.get("filename")
        current_app.logger.info(f"恢复操作请求的备份文件名: {filename}")

        # 参数校验
        if not filename or not (filename.endswith(".sql") or filename.endswith(".zip")):
            current_app.logger.warning(f"无效的备份文件名: {filename}")
            return jsonify({"success": False, "message": "无效的备份文件名"}), 400

        # 检查备份文件是否存在
        backup_file = os.path.join(BACKUP_FOLDER, filename)
        if not os.path.exists(backup_file):
            current_app.logger.warning(f"备份文件不存在: {backup_file}")
            return jsonify({"success": False, "message": "备份文件不存在"}), 404

        current_app.logger.info(f"开始从备份文件恢复: {backup_file}")
        # 执行恢复
        success = restore_database_python(backup_file)

        if success:
            current_app.logger.info(f"数据库恢复成功: {filename}")
            return jsonify({"success": True, "message": "数据库恢复成功"}), 200
        else:
            current_app.logger.error(f"数据库恢复失败: {filename}")
            return jsonify({"success": False, "message": "数据库恢复失败"}), 500
    except Exception as e:
        current_app.logger.error(f"数据库恢复失败: {str(e)}")
        return jsonify({"success": False, "message": f"数据库恢复失败: {str(e)}"}), 500


# API端点：上传并恢复备份文件
@system_bp.route("/restore/upload", methods=["POST"])
def upload_and_restore():
    """
    上传并恢复备份文件
    直接从单个包含SQL和uploads.zip的ZIP文件中恢复
    """
    try:
        from datetime import datetime
        import os
        import zipfile
        import io

        current_app.logger.info("管理员开始执行上传并恢复数据库操作")

        temp_sql_path = None
        temp_zip_path = None

        # 检查是否有上传文件
        if "file" not in request.files or request.files["file"].filename == "":
            current_app.logger.warning("未上传任何备份文件")
            return jsonify({"success": False, "message": "未上传任何备份文件"}), 400

        # 上传单个ZIP文件
        zip_file = request.files["file"]
        original_filename = zip_file.filename
        current_app.logger.info(f"上传的备份文件名: {original_filename}")

        # 检查文件名
        if not original_filename.endswith(".zip"):
            current_app.logger.warning(f"非zip格式的备份文件: {original_filename}")
            return (
                jsonify({"success": False, "message": "请上传.zip格式的备份文件"}),
                400,
            )

        # 生成备份文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_backup_filename = f"gradpush_backup_{timestamp}.zip"
        final_backup_path = os.path.join(BACKUP_FOLDER, final_backup_filename)

        # 保存上传的ZIP文件作为最终备份
        zip_file.save(final_backup_path)
        current_app.logger.info(f"上传的备份文件已保存: {final_backup_path}")

        try:
            # 打开ZIP文件并寻找SQL和ZIP文件
            with zipfile.ZipFile(final_backup_path, "r") as zipf:
                current_app.logger.info(f"开始解析备份ZIP文件: {final_backup_filename}")

                # 寻找SQL文件
                sql_files = [name for name in zipf.namelist() if name.endswith(".sql")]
                if not sql_files:
                    current_app.logger.error("ZIP文件中未找到SQL数据库备份文件")
                    raise ValueError("ZIP文件中未找到SQL数据库备份文件")

                # 使用第一个找到的SQL文件
                sql_filename = sql_files[0]
                current_app.logger.info(f"找到SQL备份文件: {sql_filename}")

                # 提取SQL文件到临时路径
                temp_sql_path = os.path.join(
                    BACKUP_FOLDER, f"temp_restore_{timestamp}.sql"
                )
                with open(temp_sql_path, "wb") as sql_out:
                    sql_out.write(zipf.read(sql_filename))
                current_app.logger.info(f"已提取SQL文件到临时路径: {temp_sql_path}")

                # 寻找uploads.zip文件
                uploads_zip_files = [
                    name for name in zipf.namelist() if "_uploads.zip" in name
                ]

                # 如果找到uploads.zip文件，提取它
                if uploads_zip_files:
                    uploads_zip_filename = uploads_zip_files[0]
                    temp_zip_path = os.path.join(
                        BACKUP_FOLDER, f"temp_restore_uploads_{timestamp}.zip"
                    )
                    with open(temp_zip_path, "wb") as zip_out:
                        zip_out.write(zipf.read(uploads_zip_filename))
                    current_app.logger.info(
                        f"已提取uploads.zip文件到临时路径: {temp_zip_path}"
                    )
        except Exception as e:
            # 如果解压失败，删除保存的备份文件
            if os.path.exists(final_backup_path):
                os.remove(final_backup_path)
            raise e

        try:
            # 恢复数据库
            current_app.logger.info(f"开始从SQL文件恢复数据库: {temp_sql_path}")
            success = restore_database_python(temp_sql_path)

            # 恢复uploads目录
            if temp_zip_path and os.path.exists(temp_zip_path):
                current_app.logger.info(f"开始恢复uploads目录: {temp_zip_path}")
                restore_uploads(temp_zip_path)
                current_app.logger.info("uploads目录恢复完成")

            if success:
                current_app.logger.info(f"数据库恢复成功: {final_backup_filename}")
                # 恢复成功后，删除临时文件
                if os.path.exists(temp_sql_path):
                    os.remove(temp_sql_path)
                    current_app.logger.info(f"删除临时SQL文件: {temp_sql_path}")
                if temp_zip_path and os.path.exists(temp_zip_path):
                    os.remove(temp_zip_path)
                    current_app.logger.info(f"删除临时uploads.zip文件: {temp_zip_path}")

                return (
                    jsonify(
                        {
                            "success": True,
                            "message": "备份恢复成功",
                            "backup_file": final_backup_filename,
                        }
                    ),
                    200,
                )
            else:
                current_app.logger.error(f"数据库恢复失败: {final_backup_filename}")
                # 恢复失败，删除临时文件和保存的备份文件
                if os.path.exists(temp_sql_path):
                    os.remove(temp_sql_path)
                if temp_zip_path and os.path.exists(temp_zip_path):
                    os.remove(temp_zip_path)
                if os.path.exists(final_backup_path):
                    os.remove(final_backup_path)
                return jsonify({"success": False, "message": "备份恢复失败"}), 500

        except Exception as e:
            current_app.logger.error(f"恢复过程中发生错误: {str(e)}")
            # 恢复失败，删除临时文件和保存的备份文件
            if os.path.exists(temp_sql_path):
                os.remove(temp_sql_path)
            if temp_zip_path and os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)
            if os.path.exists(final_backup_path):
                os.remove(final_backup_path)
            raise e

    except Exception as e:
        current_app.logger.error(f"上传并恢复数据库失败: {str(e)}")
        return jsonify({"success": False, "message": f"恢复失败: {str(e)}"}), 500


# API端点：删除备份
@system_bp.route("/backup/delete/<string:filename>", methods=["DELETE"])
def delete_backup(filename):
    """
    删除备份文件(只删除完整的ZIP备份文件)
    """
    try:
        current_app.logger.info(f"管理员开始删除备份文件: {filename}")

        if not filename:
            current_app.logger.warning("删除备份失败: 缺少备份文件名")
            return jsonify({"success": False, "message": "缺少备份文件名"}), 400

        # 检查备份文件是否存在
        backup_file = os.path.join(BACKUP_FOLDER, filename)
        if not os.path.exists(backup_file):
            current_app.logger.warning(f"删除备份失败: 备份文件不存在 {filename}")
            return jsonify({"success": False, "message": "备份文件不存在"}), 404

        # 只允许删除完整的备份ZIP文件
        if not (filename.startswith("gradpush_backup_") and filename.endswith(".zip")):
            current_app.logger.warning(
                f"删除备份失败: 只能删除完整的备份ZIP文件 {filename}"
            )
            return (
                jsonify({"success": False, "message": "只能删除完整的备份ZIP文件"}),
                400,
            )

        # 删除完整的备份ZIP文件
        os.remove(backup_file)
        current_app.logger.info(f"成功删除备份ZIP文件: {backup_file}")

        # 同步删除对应的uploads备份文件
        uploads_backup_filename = filename.replace(".zip", "_uploads.zip")
        uploads_backup_file = os.path.join(BACKUP_FOLDER, uploads_backup_filename)
        if os.path.exists(uploads_backup_file):
            os.remove(uploads_backup_file)
            current_app.logger.info(
                f"已同步删除对应的uploads备份文件: {uploads_backup_filename}"
            )

        current_app.logger.info(f"备份文件删除操作完成: {filename}")
        return jsonify({"success": True, "message": "备份文件删除成功"}), 200
    except Exception as e:
        current_app.logger.error(f"删除备份文件失败: {str(e)}")
        return (
            jsonify({"success": False, "message": f"删除备份文件失败: {str(e)}"}),
            500,
        )


# API端点：获取系统日志文件列表
@system_bp.route("/logs", methods=["GET"])
def get_system_logs():
    """
    获取系统日志文件列表
    """
    try:
        # 简单实现：返回系统日志文件列表
        log_files = []
        if os.path.exists(LOG_FOLDER):
            for filename in os.listdir(LOG_FOLDER):
                filepath = os.path.join(LOG_FOLDER, filename)
                if os.path.isfile(filepath):
                    file_info = {
                        "name": filename,
                        "size": os.path.getsize(filepath),
                        "create_time": datetime.fromtimestamp(
                            os.path.getctime(filepath)
                        ).isoformat(),
                        "download_url": f"/api/system/log/download/{filename}",
                    }
                    log_files.append(file_info)

        # 按创建时间降序排序
        log_files.sort(key=lambda x: x["create_time"], reverse=True)

        return jsonify({"success": True, "logs": log_files}), 200
    except Exception as e:
        current_app.logger.error(f"获取系统日志失败: {str(e)}")
        return (
            jsonify({"success": False, "message": f"获取系统日志失败: {str(e)}"}),
            500,
        )


# API端点：下载日志文件
@system_bp.route("/log/download/<filename>", methods=["GET"])
def download_log(filename):
    """
    下载日志文件
    """
    try:
        return send_from_directory(LOG_FOLDER, filename, as_attachment=True)
    except Exception as e:
        current_app.logger.error(f"下载日志文件失败: {str(e)}")
        return (
            jsonify({"success": False, "message": f"下载日志文件失败: {str(e)}"}),
            500,
        )


# API端点：查看日志内容
@system_bp.route("/log/view/<filename>", methods=["GET"])
def view_log_content(filename):
    """
    查看日志文件内容
    """
    try:
        # 获取日志文件路径
        log_path = os.path.join(LOG_FOLDER, filename)

        # 检查文件是否存在
        if not os.path.exists(log_path):
            return jsonify({"success": False, "message": "日志文件不存在"}), 404

        # 读取日志文件内容，尝试多种编码方式
        content = ""
        encodings_to_try = ["utf-8", "gbk", "gb2312", "ansi"]

        for encoding in encodings_to_try:
            try:
                with open(log_path, "r", encoding=encoding, errors="ignore") as f:
                    content = f.read()
                    break  # 成功读取后跳出循环
            except UnicodeDecodeError:
                continue  # 尝试下一种编码

        if not content:
            # 如果所有编码都失败，使用二进制模式读取并转换为字符串
            with open(log_path, "rb") as f:
                content = f.read().decode("utf-8", errors="replace")

        return jsonify({"success": True, "content": content, "filename": filename}), 200
    except Exception as e:
        current_app.logger.error(f"查看日志文件内容失败: {str(e)}")
        return (
            jsonify({"success": False, "message": f"查看日志文件内容失败: {str(e)}"}),
            500,
        )


# API端点：清理缓存
@system_bp.route("/cache/clear", methods=["POST"])
def clear_cache():
    """
    清理系统缓存
    """
    try:
        # 清理缓存文件夹中的所有文件
        if os.path.exists(CACHE_FOLDER):
            for filename in os.listdir(CACHE_FOLDER):
                filepath = os.path.join(CACHE_FOLDER, filename)
                try:
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                    elif os.path.isdir(filepath):
                        shutil.rmtree(filepath)
                except Exception as file_error:
                    current_app.logger.error(f"清理{filepath}失败: {str(file_error)}")

        return jsonify({"success": True, "message": "系统缓存清理成功"}), 200
    except Exception as e:
        current_app.logger.error(f"清理缓存失败: {str(e)}")
        return jsonify({"success": False, "message": f"清理缓存失败: {str(e)}"}), 500
