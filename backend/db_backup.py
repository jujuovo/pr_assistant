# -*- coding: utf-8 -*-
"""
数据库备份与恢复脚本

该脚本用于备份和恢复PostgreSQL数据库，基于项目的配置文件获取数据库连接信息。
同时备份和恢复uploads目录下的实际文件。
"""

import os
import sys
import psycopg2
import argparse
import zipfile
import shutil
from datetime import datetime
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


def get_db_connection():
    """
    获取数据库连接
    """
    try:
        # 直接使用完整的连接字符串，避免解析过程中的编码问题
        db_uri = Config.SQLALCHEMY_DATABASE_URI
        
        # 确保连接字符串是字符串类型
        if isinstance(db_uri, bytes):
            db_uri = db_uri.decode('utf-8', errors='replace')
        
        # 直接传递完整的连接字符串给psycopg2.connect()
        conn = psycopg2.connect(db_uri)
        return conn
    except Exception as e:
        print(f"连接数据库失败: {e}")
        print(f"数据库连接字符串: {Config.SQLALCHEMY_DATABASE_URI}")
        # 抛出异常而不是退出程序，让调用者处理错误
        raise e


def backup_uploads(backup_file):
    """
    备份uploads目录
    """
    # 获取uploads目录路径
    uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")

    if not os.path.exists(uploads_dir):
        print(f"警告: uploads目录不存在 - {uploads_dir}")
        return

    print(f"开始备份uploads目录到 {backup_file}...")

    # 创建zip文件
    with zipfile.ZipFile(backup_file, "w", zipfile.ZIP_DEFLATED) as zipf:
        # 遍历uploads目录并添加所有文件
        for root, dirs, files in os.walk(uploads_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # 计算相对路径，保留目录结构
                arcname = os.path.relpath(file_path, uploads_dir)
                zipf.write(file_path, arcname)

    print(f"uploads目录备份完成: {backup_file}")


def backup_database(backup_file):
    """
    备份数据库
    """
    print(f"开始备份数据库到 {backup_file}...")

    # 使用psycopg2执行pg_dump命令
    result = os.system(
        f"pg_dump -h localhost -p 5432 -U postgres -d gradpush -f {backup_file} --password"
    )

    if result != 0:
        raise Exception(f"pg_dump命令执行失败，退出码: {result}")

    print(f"数据库备份完成: {backup_file}")

    # 同时备份uploads目录
    uploads_backup = backup_file.replace(".sql", "_uploads.zip")
    backup_uploads(uploads_backup)


def backup_database_python(backup_file):
    """
    使用Python代码备份数据库（备选方案，当pg_dump不可用时）
    """
    print(f"开始使用Python备份数据库到 {backup_file}...")

    conn = get_db_connection()
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    try:
        # 创建备份文件
        with open(backup_file, "wb") as f:
            # 第一步：备份所有序列
            print("备份序列...")
            # 使用pg_get_serial_sequence获取所有表的序列
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
                    f.write(f"-- 序列: {seq_name}".encode('utf-8'))

                    try:
                        # 简化序列备份：只备份当前值，不尝试重建完整序列定义
                        f.write(f"\n-- 序列当前值: {seq_name}\n".encode('utf-8'))

                        # 设置序列当前值
                        cursor.execute(f"SELECT last_value FROM {seq_name}")
                        last_val = cursor.fetchone()[0]
                        f.write(f"SELECT setval('{seq_name}', {last_val}, true);\n\n".encode('utf-8'))
                    except Exception as e:
                        print(f"  备份序列 {seq_name} 失败: {e}")
                        f.write(f"-- 备份序列 {seq_name} 失败\n\n".encode('utf-8'))

            # 第二步：备份所有表结构和数据
            cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"
            )
            tables = cursor.fetchall()

            for table in tables:
                table_name = table[0]
                print(f"备份表: {table_name}")

                # 备份表结构
                f.write(f"-- 表结构: {table_name}\n".encode('utf-8'))

                # 处理保留关键字表名
                quoted_table_name = (
                    f'"{table_name}"'
                    if table_name.lower()
                    in [
                        "user",
                        "order",
                        "group",
                        "select",
                        "insert",
                        "update",
                        "delete",
                    ]
                    else table_name
                )

                f.write(f"CREATE TABLE {quoted_table_name} (\n".encode('utf-8'))

                # 获取表列信息
                cursor.execute(
                    """
                    SELECT column_name, data_type, character_maximum_length, column_default, is_nullable 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position
                """,
                    (table_name,),
                )
                columns = cursor.fetchall()

                column_definitions = []
                for col in columns:
                    col_name, data_type, max_length, default, is_nullable = col
                    col_def = f"    {col_name} {data_type}"

                    if max_length is not None:
                        col_def += f"({max_length})"

                    if default is not None:
                        col_def += f" DEFAULT {default}"

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
                    column_definitions.append(
                        f"    PRIMARY KEY ({', '.join(pkey_cols)})"
                    )

                f.write(",\n".join(column_definitions).encode('utf-8'))
                f.write("\n);\n\n".encode('utf-8'))

                # 备份表数据
                cursor.execute(f"SELECT * FROM {quoted_table_name}")
                rows = cursor.fetchall()

                if rows:
                    f.write(f"-- 表数据: {table_name}\n".encode('utf-8'))
                    column_names = [desc[0] for desc in cursor.description]

                    for row in rows:
                        # 处理特殊字符
                        values = []
                        for value in row:
                            if value is None:
                                values.append("NULL")
                            elif isinstance(value, str):
                                # 转义单引号并确保UTF-8编码
                                try:
                                    # 尝试直接编码为UTF-8
                                    escaped_value = value.replace("'", "''")
                                    values.append(f"'{escaped_value}'".encode('utf-8'))
                                except UnicodeEncodeError:
                                    # 如果编码失败，尝试使用utf-8-sig或忽略错误
                                    escaped_value = value.replace("'", "''")
                                    values.append(f"'{escaped_value}'".encode('utf-8', 'ignore'))
                            elif isinstance(value, datetime):
                                values.append(f"'{value}'".encode('utf-8'))
                            elif isinstance(value, list):
                                # 处理列表/数组类型，转换为JSON格式
                                import json

                                json_str = json.dumps(value)
                                values.append(f"'{json_str.replace("'", "''")}'".encode('utf-8'))
                            else:
                                values.append(str(value).encode('utf-8'))

                        # 构建插入语句
                        col_names_str = ', '.join(column_names).encode('utf-8')
                        values_str = b', '.join(values)
                        insert_sql = b"INSERT INTO " + quoted_table_name.encode('utf-8') + b" (" + col_names_str + b") VALUES (" + values_str + b");\n"
                        f.write(insert_sql)
                    f.write("\n".encode('utf-8'))

        print(f"数据库备份完成: {backup_file}")

        # 同时备份uploads目录
        uploads_backup = backup_file.replace(".sql", "_uploads.zip")
        backup_uploads(uploads_backup)

    except Exception as e:
        print(f"备份数据库失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


def restore_uploads(backup_file):
    """
    恢复uploads目录
    """
    # 确保必要的模块已导入
    import os
    import shutil
    import tempfile
    import zipfile
    from datetime import datetime

    # 获取当前时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]

    # 获取uploads目录路径
    uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")

    # 如果uploads目录不存在，创建它
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
        print(f"创建uploads目录: {uploads_dir}")
    else:
        # 清空现有uploads目录内容
        for item in os.listdir(uploads_dir):
            item_path = os.path.join(uploads_dir, item)
            if os.path.isfile(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        print(f"清空现有uploads目录: {uploads_dir}")

    # 确定上传文件备份的位置
    uploads_backup = None
    is_direct_uploads_zip = False

    # 检查backup_file是否是直接的uploads备份文件
    if backup_file.endswith("_uploads.zip"):
        print(f"识别到直接的uploads备份文件: {backup_file}")
        uploads_backup = backup_file
        is_direct_uploads_zip = True
    # 如果是完整的zip备份文件
    elif backup_file.endswith(".zip"):
        print(f"识别到完整ZIP备份文件: {backup_file}")
        uploads_backup = backup_file
    else:
        # 查找对应的uploads备份文件
        uploads_backup = backup_file.replace(".sql", "_uploads.zip")

    if not os.path.exists(uploads_backup):
        print(f"警告: 未找到uploads备份文件 - {uploads_backup}")
        return

    print(f"开始从 {uploads_backup} 恢复uploads目录...")

    # 使用zipfile打开备份文件
    with zipfile.ZipFile(uploads_backup, "r") as zipf:
        # 列出ZIP文件内容，用于调试
        print(f"ZIP文件包含内容: {zipf.namelist()}")

        if is_direct_uploads_zip:
            # 如果是直接的uploads备份文件，直接解压所有内容到uploads目录
            zipf.extractall(uploads_dir)
            print(f"uploads目录恢复完成: {uploads_dir}")
            return

        # 查找内部的_uploads.zip文件
        inner_files = zipf.namelist()
        # 使用更宽松的匹配条件，查找任何包含'uploads'的ZIP文件
        uploads_zip_file = next(
            (f for f in inner_files if "_uploads" in f and f.endswith(".zip")), None
        )

        if uploads_zip_file:
            print(f"找到内部uploads备份文件: {uploads_zip_file}")
            # 直接从ZIP中读取内部uploads ZIP文件的内容
            uploads_zip_content = zipf.read(uploads_zip_file)

            # 使用临时文件保存内部uploads ZIP内容
            temp_uploads_zip_path = os.path.join(
                os.path.dirname(__file__), f"temp_uploads_{timestamp}.zip"
            )
            try:
                with open(temp_uploads_zip_path, "wb") as temp_file:
                    temp_file.write(uploads_zip_content)

                # 打开提取的_uploads.zip文件并解压到uploads目录
                with zipfile.ZipFile(temp_uploads_zip_path, "r") as inner_zipf:
                    # 列出内部ZIP文件内容，用于调试
                    print(f"内部uploads.zip文件包含: {inner_zipf.namelist()}")

                    # 解压所有文件到uploads目录
                    inner_zipf.extractall(uploads_dir)

                print(f"uploads目录恢复完成: {uploads_dir}")
                print(f"恢复的文件数量: {len(inner_zipf.namelist())}")
                return
            except Exception as e:
                print(f"处理内部uploads.zip文件时发生错误: {str(e)}")
                import traceback

                traceback.print_exc()
            finally:
                # 确保临时文件被删除，即使发生错误
                if os.path.exists(temp_uploads_zip_path):
                    try:
                        os.remove(temp_uploads_zip_path)
                    except Exception as e:
                        print(f"删除临时文件时发生错误: {str(e)}")

        # 处理完整备份文件中的直接文件提取
        # 如果找不到内部的_uploads.zip文件，直接从完整备份中提取文件
        if not uploads_zip_file:
            print(f"未找到内部uploads.zip文件，直接从完整备份中提取文件...")
            for member in zipf.infolist():
                if not member.is_dir() and member.filename:
                    # 直接提取文件到uploads目录
                    target_path = os.path.join(uploads_dir, member.filename)
                    # 创建目标目录
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    # 提取文件
                    with zipf.open(member) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
            print(f"直接从完整备份提取文件完成")

    print(f"uploads目录恢复完成: {uploads_dir}")


def restore_database(backup_file):
    """
    恢复数据库
    """
    print(f"开始从 {backup_file} 恢复数据库...")

    # 先恢复uploads目录
    restore_uploads(backup_file)

    # 解析数据库连接字符串
    db_uri = Config.SQLALCHEMY_DATABASE_URI
    db_uri = db_uri.split("://")[1]
    user_pass_part, host_db_part = db_uri.split("@")
    user = user_pass_part.split(":")[0]
    password = user_pass_part.split(":")[1]
    host_port_part, dbname = host_db_part.split("/")
    host = host_port_part.split(":")[0]
    port = host_port_part.split(":")[1]

    # 使用配置文件中的数据库连接信息执行psql命令
    # 设置PGPASSWORD环境变量避免密码提示
    os.environ["PGPASSWORD"] = password
    result = os.system(
        f"psql -h {host} -p {port} -U {user} -d {dbname} -f {backup_file}"
    )
    # 删除环境变量
    del os.environ["PGPASSWORD"]

    if result != 0:
        raise Exception(f"psql命令执行失败，退出码: {result}")

    print(f"数据库恢复完成")


def restore_database_python(backup_file):
    """
    使用Python代码恢复数据库（备选方案，当psql不可用时）
    """
    print(f"开始使用Python从 {backup_file} 恢复数据库...")

    # 先恢复uploads目录
    restore_uploads(backup_file)

    conn = get_db_connection()
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    try:
        # 第一步：从备份文件中提取所有引用的序列
        print("提取备份文件中的序列信息...")

        # 检查文件是否为zip格式
        if backup_file.endswith(".zip"):
            import zipfile

            print(f"识别到ZIP格式备份文件，正在提取SQL内容...")
            with zipfile.ZipFile(backup_file, "r") as zipf:
                # 查找zip文件中的SQL文件
                sql_files = [f for f in zipf.namelist() if f.endswith(".sql")]
                if not sql_files:
                    raise Exception("ZIP文件中未找到SQL文件")

                # 读取SQL文件内容
                sql_file = sql_files[0]
                with zipf.open(sql_file, "r") as f:
                    binary_content = f.read()
        else:
            # 以二进制模式读取普通SQL文件
            with open(backup_file, "rb") as f:
                binary_content = f.read()

        # 使用utf-8解码，忽略无法解码的字符
        content = binary_content.decode("utf-8", errors="replace")
        print("成功使用utf-8编码（忽略错误）读取备份文件")

        # 查找所有引用的序列：nextval('sequence_name'::regclass)
        import re

        sequence_pattern = r"nextval\('([^']+)\'::regclass"
        sequences = set(re.findall(sequence_pattern, content))

        print(f"备份文件中引用的序列: {', '.join(sequences)}")

        # 第二步：创建所有序列
        if sequences:
            print("创建必要的序列...")
            for seq in sequences:
                try:
                    # 尝试创建序列
                    cursor.execute(f"CREATE SEQUENCE {seq} START 1;")
                    print(f"  创建序列 {seq} 成功")
                except Exception as e:
                    # 如果序列已存在，忽略错误
                    if "already exists" in str(e):
                        print(f"  序列 {seq} 已存在")
                    else:
                        print(f"  创建序列 {seq} 失败: {e}")

        # 第三步：提取表名（已经有content变量，无需再次读取文件）
        print("提取备份文件中的表信息...")
        table_names = []
        current_table = None
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("CREATE TABLE"):
                # 提取表名
                parts = line.split()
                if len(parts) >= 3:
                    table_name = parts[2]
                    # 处理可能的引号
                    if table_name.startswith('"') and table_name.endswith('"'):
                        table_name = table_name[1:-1]
                    table_names.append(table_name)

        print(f"备份文件中包含的表: {', '.join(table_names)}")

        # 第四步：获取当前数据库中的所有表
        cursor.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        existing_tables = [row[0] for row in cursor.fetchall()]

        # 第五步：删除所有表以准备恢复（确保干净的恢复环境）
        tables_to_drop = existing_tables
        if tables_to_drop:
            print(f"删除所有现有表以准备恢复: {', '.join(tables_to_drop)}")

            # 首先禁用外键约束
            cursor.execute("SET session_replication_role = 'replica'")

            # 删除表（逆序删除，避免外键约束问题）
            for table in reversed(tables_to_drop):
                try:
                    # 处理保留关键字，如表名是user等
                    quoted_table = (
                        f'"{table}"'
                        if table.lower()
                        in [
                            "user",
                            "order",
                            "group",
                            "select",
                            "insert",
                            "update",
                            "delete",
                        ]
                        else table
                    )
                    cursor.execute(f"DROP TABLE IF EXISTS {quoted_table} CASCADE")
                    print(f"已删除表: {table}")
                except Exception as e:
                    print(f"删除表 {table} 失败: {e}")

            # 重置序列（处理自动递增的ID）
            cursor.execute(
                "SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public'"
            )
            sequences = [row[0] for row in cursor.fetchall()]
            for seq in sequences:
                try:
                    cursor.execute(f"DROP SEQUENCE IF EXISTS {seq} CASCADE")
                    print(f"已删除序列: {seq}")
                except Exception as e:
                    print(f"删除序列 {seq} 失败: {e}")

            # 重新启用外键约束
            cursor.execute("SET session_replication_role = 'origin'")

        # 第六步：从备份文件中提取并创建所有需要的序列
        print("从备份文件中提取并创建序列...")
        import re

        # 从备份文件中提取所有序列名
        sequences_to_create = set()
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("SELECT setval"):
                # 提取序列名
                match = re.search(r"'public\.([^']+)'", line)
                if match:
                    sequence_name = match.group(1)
                    sequences_to_create.add(sequence_name)

        print(f"需要创建的序列: {', '.join(sequences_to_create)}")

        for seq in sequences_to_create:
            try:
                cursor.execute(
                    f"CREATE SEQUENCE IF NOT EXISTS {seq} START WITH 1 INCREMENT BY 1"
                )
                print(f"已创建序列: {seq}")
            except Exception as e:
                print(f"创建序列 {seq} 失败: {e}")

        # 第七步：执行备份文件中的SQL命令（已经有content变量，无需再次读取文件）
        print("执行备份文件中的SQL命令...")
        sql_content = content

        # 处理保留关键字：将CREATE TABLE user替换为CREATE TABLE "user"
        sql_content = sql_content.replace("CREATE TABLE user", 'CREATE TABLE "user"')
        sql_content = sql_content.replace("INSERT INTO user", 'INSERT INTO "user"')
        
        # 检查SQL内容中是否包含captcha表的创建和插入语句
        if "CREATE TABLE captcha" not in sql_content:
            print("警告：备份文件中未找到captcha表的创建语句，将自动添加")
            # 添加captcha表的创建语句
            captcha_table_sql = """
-- 创建captcha表
CREATE TABLE IF NOT EXISTS captcha (
    id SERIAL PRIMARY KEY,
    token VARCHAR(36) UNIQUE NOT NULL,
    text VARCHAR(10) NOT NULL,
    user_identifier VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    expired_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_captcha_token ON captcha(token);
CREATE INDEX IF NOT EXISTS idx_captcha_user_identifier ON captcha(user_identifier);
            """
            sql_content = captcha_table_sql + "\n" + sql_content

        # 预处理：将Python字典语法转换为PostgreSQL的JSON语法
        import re
        import json
        import ast

        # 重写的JSON处理方法，使用正则表达式直接匹配并修复字段
        def fix_json_fields(line):
            import re

            # 替换空值
            line = line.replace("'None'", "NULL")
            line = line.replace("None", "NULL")

            # 专门处理application表的INSERT语句
            if "INSERT INTO" in line and "application" in line:
                # 修复award_date字段 - 在项目名称和描述之间
                # 匹配模式：'项目名称', YYYY-MM-DD, '描述'
                line = re.sub(
                    r"('(?:[^'\\]|\\.)*')\s*,\s*(\d{4}-\d{2}-\d{2})\s*,\s*('(?:[^'\\]|\\.)*')",
                    r"\1, '\2', \3",
                    line,
                    count=1,
                )

                # 修复dynamic_coefficients字段 - 在VALUES末尾
                # 匹配模式：, {'tree_path': [...]})
                pattern = r",\s*({'tree_path':\s*\[[^\]]+\]})\s*\);?"
                match = re.search(pattern, line)
                if match:
                    dict_str = match.group(1)
                    try:
                        # 将Python字典转换为JSON
                        dict_obj = ast.literal_eval(dict_str)
                        json_str = json.dumps(dict_obj, ensure_ascii=False)
                        # 替换原字典为带单引号的JSON字符串
                        line = line.replace(dict_str, f"'{json_str}'")
                    except Exception:
                        pass  # 忽略解析失败，保持原样

            # 处理rule_calculation表的INSERT语句
            if "INSERT INTO" in line and "rule_calculation" in line:
                # 改进的方法：找到parameters字段的值部分
                # 匹配模式：'parameters'字段对应的值是一个Python字典

                # 查找parameters字段的位置
                param_start = line.find("'parameters'", 0)
                if param_start == -1:
                    param_start = line.find('"parameters"', 0)

                if param_start != -1:
                    # 找到parameters字段后的左括号位置
                    left_brace = line.find("{", param_start)
                    if left_brace != -1:
                        # 使用括号匹配找到完整的字典（包括嵌套结构）
                        brace_count = 1
                        right_brace = left_brace + 1
                        while right_brace < len(line) and brace_count > 0:
                            if line[right_brace] == "{":
                                brace_count += 1
                            elif line[right_brace] == "}":
                                brace_count -= 1
                            right_brace += 1

                        # 提取完整的字典字符串
                        dict_str = line[left_brace:right_brace]
                        try:
                            # 先将NULL替换为None，因为ast.literal_eval()只识别None
                            dict_str_for_eval = dict_str.replace("NULL", "None")
                            # 将Python字典转换为JSON
                            dict_obj = ast.literal_eval(dict_str_for_eval)
                            json_str = json.dumps(dict_obj, ensure_ascii=False)
                            # 替换原字典为带单引号的JSON字符串
                            line = (
                                line[:left_brace] + f"'{json_str}'" + line[right_brace:]
                            )
                        except Exception:
                            pass  # 忽略解析失败，保持原样

            return line

        # 应用修复
        lines = sql_content.split("\n")
        fixed_lines = []
        for line in lines:
            if "INSERT INTO" in line and (
                "application" in line or "rule_calculation" in line
            ):
                try:
                    fixed_line = fix_json_fields(line)
                    line = fixed_line
                except Exception as e:
                    print(f"修复JSON字段失败: {e}")
                    print(f"失败的行: {line}")
                    print("跳过该行的JSON字段修复，继续执行恢复...")
            fixed_lines.append(line)
        sql_content = "\n".join(fixed_lines)

        # 执行整个SQL内容
        try:
            cursor.execute(sql_content)
            print("备份文件中的SQL命令执行完成")
        except Exception as e:
            print(f"执行SQL命令失败: {e}")
            print(f"尝试分段执行...")

            # 优化SQL分割逻辑，确保所有命令都能被正确分割
            # 先将SQL内容按行分割
            lines = sql_content.split("\n")
            sql_commands = []
            current_command = ""

            for line in lines:
                stripped_line = line.strip()
                # 跳过空行和注释行
                if not stripped_line or stripped_line.startswith("--"):
                    continue

                current_command += line + "\n"

                # 如果行以分号结尾，说明是一个完整的命令
                if stripped_line.endswith(";"):
                    sql_commands.append(current_command.strip())
                    current_command = ""

            # 处理最后一个命令（如果没有分号结尾）
            if current_command.strip():
                sql_commands.append(current_command.strip())

            print(f"共发现 {len(sql_commands)} 条SQL命令")

            # 执行所有SQL命令
            command_count = 0
            table_creation_count = 0
            insert_count = 0
            error_count = 0

            for command in sql_commands:
                command_count += 1
                try:
                    # 对每个SQL命令应用修复，特别是INSERT INTO命令
                    if command.startswith(
                        "INSERT INTO application"
                    ) or command.startswith("INSERT INTO rule_calculation"):
                        try:
                            command = fix_json_fields(command)
                        except Exception as e:
                            print(f"修复JSON字段失败: {e}")
                            print("跳过该命令的JSON字段修复，继续执行恢复...")
                    cursor.execute(command)
                    if command.startswith("CREATE TABLE"):
                        table_creation_count += 1
                        # 处理包含IF NOT EXISTS的情况
                        parts = command.split()
                        if len(parts) > 3 and parts[2] == "IF":
                            # 跳过IF NOT EXISTS
                            table_name = parts[5] if len(parts) > 5 else parts[-1]
                        else:
                            table_name = parts[2]
                        if table_name.startswith('"') and table_name.endswith('"'):
                            table_name = table_name[1:-1]
                        print(f"已创建表: {table_name}")
                    elif command.startswith("INSERT INTO"):
                        insert_count += 1
                        if insert_count % 10 == 0:
                            print(f"已插入 {insert_count} 条记录")

                    if command_count % 20 == 0:  # 每执行20条命令显示进度
                        print(f"已执行 {command_count} 条命令")
                except Exception as e:
                    print(f"执行SQL命令失败 (第{command_count}条): {e}")
                    print(f"失败的命令: {command[:200]}...")
                    error_count += 1
                    # 继续执行下一条命令，而不是立即终止
                    print("跳过该命令，继续执行下一条")

            print(
                f"分段执行完成，共执行 {command_count} 条命令，成功 {command_count - error_count} 条，失败 {error_count} 条"
            )
            
            # 如果有错误发生，返回False
            if error_count > 0:
                return False

        print(f"数据库恢复完成")

    except Exception as e:
        print(f"恢复数据库失败: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        cursor.close()
        conn.close()

    return True


def main():
    parser = argparse.ArgumentParser(description="数据库备份与恢复工具")
    parser.add_argument(
        "action",
        choices=["backup", "restore"],
        help="操作类型: backup(备份) 或 restore(恢复)",
    )
    parser.add_argument("file", help="备份文件路径")
    parser.add_argument(
        "--python-only",
        action="store_true",
        help="仅使用Python代码执行备份/恢复，不依赖pg_dump/psql命令",
    )

    args = parser.parse_args()

    if args.action == "backup":
        if args.python_only:
            backup_database_python(args.file)
        else:
            try:
                backup_database(args.file)
            except Exception as e:
                print(f"使用pg_dump备份失败，尝试使用Python代码备份: {e}")
                backup_database_python(args.file)
    elif args.action == "restore":
        if args.python_only:
            restore_database_python(args.file)
        else:
            try:
                restore_database(args.file)
            except Exception as e:
                print(f"使用psql恢复失败，尝试使用Python代码恢复: {e}")
                restore_database_python(args.file)


if __name__ == "__main__":
    main()
