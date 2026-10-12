#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PostgreSQL数据库初始化脚本
根据models.py中的模型定义创建数据库表
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# 导入配置和模型
from app import app
from models import *
from extensions import db

def init_database():
    """
    初始化数据库：创建所有表结构
    """
    print("开始初始化PostgreSQL数据库...")
    
    try:
        # 使用Flask应用上下文
        with app.app_context():
            # 创建所有表
            db.create_all()
            
            print("✓ 数据库表创建成功")
            
            # 初始化一些基础数据
            init_base_data()
            
            print("✓ 基础数据初始化完成")
            print("\n数据库初始化成功！")
        
    except Exception as e:
        print(f"✗ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def init_base_data():
    """
    初始化基础数据
    """
    print("开始初始化基础数据...")
    
    try:
        # 检查是否已有数据
        existing_faculty = Faculty.query.first()
        if existing_faculty:
            print("✓ 基础数据已存在，跳过初始化")
            return
        
        # 1. 创建学院
        faculties = [
            Faculty(name="计算机科学与技术学院", description="计算机科学与技术相关专业学院"),
            Faculty(name="电子信息工程学院", description="电子信息工程相关专业学院"),
            Faculty(name="经济管理学院", description="经济管理相关专业学院"),
            Faculty(name="外国语学院", description="外国语言文学相关专业学院"),
        ]
        db.session.add_all(faculties)
        db.session.flush()  # 获取学院ID
        
        # 2. 创建系
        departments = [
            Department(name="计算机科学系", faculty_id=faculties[0].id),
            Department(name="软件工程系", faculty_id=faculties[0].id),
            Department(name="电子工程系", faculty_id=faculties[1].id),
            Department(name="信息工程系", faculty_id=faculties[1].id),
            Department(name="经济系", faculty_id=faculties[2].id),
            Department(name="管理系", faculty_id=faculties[2].id),
            Department(name="英语系", faculty_id=faculties[3].id),
            Department(name="日语系", faculty_id=faculties[3].id),
        ]
        db.session.add_all(departments)
        db.session.flush()  # 获取系ID
        
        # 3. 创建专业
        majors = [
            Major(name="计算机科学与技术", department_id=departments[0].id),
            Major(name="软件工程", department_id=departments[1].id),
            Major(name="电子信息工程", department_id=departments[2].id),
            Major(name="通信工程", department_id=departments[3].id),
            Major(name="经济学", department_id=departments[4].id),
            Major(name="工商管理", department_id=departments[5].id),
            Major(name="英语", department_id=departments[6].id),
            Major(name="日语", department_id=departments[7].id),
        ]
        db.session.add_all(majors)
        
        # 4. 创建默认管理员用户
        admin_user = User(
            username="admin",
            name="系统管理员",
            role="admin",
            status="active"
        )
        admin_user.set_password("123456")  # 设置默认密码
        db.session.add(admin_user)
        
        # 5. 创建系统设置
        system_settings = SystemSettings(
            academic_year="2025",
            single_file_size_limit=10,
            total_file_size_limit=50,
            avatar_file_size_limit=2,
            allowed_file_types=".pdf, .jpg, .jpeg, .png",
            system_status="online"
        )
        db.session.add(system_settings)
        
        # 提交所有更改
        db.session.commit()
        
        print("✓ 基础数据创建完成")
        
    except Exception as e:
        db.session.rollback()
        print(f"✗ 基础数据初始化失败: {e}")
        import traceback
        traceback.print_exc()

def drop_all_tables():
    """
    删除所有表（谨慎使用）
    """
    print("警告：即将删除所有数据库表！")
    confirm = input("请输入 'YES' 确认删除: ")
    
    if confirm == "YES":
        try:
            # 使用Flask应用上下文
            with app.app_context():
                db.drop_all()
            print("✓ 所有表已删除")
        except Exception as e:
            print(f"✗ 删除表失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("✓ 取消删除操作")

def main():
    """
    主函数
    """
    print("=== PostgreSQL数据库初始化工具 ===")
    print("1. 初始化数据库表和基础数据")
    print("2. 删除所有数据库表（谨慎使用）")
    print("3. 退出")
    
    choice = input("请选择操作 (1-3): ")
    
    if choice == "1":
        init_database()
    elif choice == "2":
        drop_all_tables()
    elif choice == "3":
        print("退出工具")
        sys.exit(0)
    else:
        print("无效选择，请重新运行工具")
        sys.exit(1)

# 添加自动运行功能，用于测试
if __name__ == "__main__":
    # 检查是否有命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        # 自动执行初始化操作
        init_database()
    else:
        # 正常运行交互式界面
        main()
