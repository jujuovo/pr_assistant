# -*- coding: utf-8 -*-
"""
学生成绩管理蓝图

该文件负责处理学生信息管理和成绩相关的API端点，包括：
- 学生信息管理（CRUD）
- 学生排名查询
- 综合成绩计算
- 学生统计数据更新
"""

from hashlib import sha256
from json import dumps

from flask import Blueprint, request, jsonify, current_app
from models import (
    User,
    Faculty,
    Department,
    Major,
    Student,
    SystemSettings,
    FacultyScoreSettings,
)
from extensions import db
from sqlalchemy import func
from services.actors import actor
from services.academic_score_import import plan_score_rows, read_score_rows
from itsdangerous import BadData, URLSafeTimedSerializer


DERIVED_STUDENT_FIELDS = frozenset({
    "academic_specialty_total", "specialty_score",
    "comprehensive_performance_total", "performance_score",
    "total_score", "comprehensive_score", "total_comprehensive_score",
    "final_comprehensive_score", "final_score", "major_ranking",
    "ranking", "ranking_count", "total_students",
})

# 创建蓝图实例
score_bp = Blueprint("score", __name__, url_prefix="/api")


# 辅助函数：更新学生的统计数据
def update_student_statistics(student_id, commit=True):
    """
    根据学生的已通过申请更新其统计数据
    :param student_id: 学生ID
    :return: 更新后的统计数据
    """
    # 查询学生的所有已通过申请
    from legacy_models import Application
    applications = Application.query.filter_by(
        student_id=student_id, status="approved"
    ).all()

    # 按申请类型分类统计
    academic_score_calculated = sum(
        app.final_score
        for app in applications
        if app.final_score is not None and app.application_type == "academic"
    )
    comprehensive_score = sum(
        app.final_score
        for app in applications
        if app.final_score is not None and app.application_type == "comprehensive"
    )

    # 获取学生对象
    student = Student.query.filter_by(student_id=student_id).first()
    if not student:
        return None

    # 获取学生所在学院的成绩设置
    faculty_score_settings = FacultyScoreSettings.query.filter_by(
        faculty_id=student.faculty_id
    ).first()

    # 应用满分限制
    if faculty_score_settings:
        academic_score_calculated = min(
            academic_score_calculated, faculty_score_settings.specialty_max_score
        )
        comprehensive_score = min(
            comprehensive_score, faculty_score_settings.performance_max_score
        )
    else:
        # 如果没有学院成绩设置，使用默认值
        academic_score_calculated = min(
            academic_score_calculated, 15.0
        )  # 默认学术专长满分15分
        comprehensive_score = min(comprehensive_score, 5.0)  # 默认综合表现满分5分

    # 更新学生统计数据
    student.academic_specialty_total = (
        academic_score_calculated  # 学术专长总分（已应用满分限制）
    )
    student.comprehensive_performance_total = (
        comprehensive_score  # 综合表现总分（已应用满分限制）
    )

    # 计算综合成绩：学业成绩 * 学业成绩权重 / 100 + 学术专长总分 + 综合表现总分
    academic_score = student.academic_score or 0.0
    specialty_total = student.academic_specialty_total or 0.0
    performance_total = student.comprehensive_performance_total or 0.0

    if faculty_score_settings:
        calculated_score = (
            (academic_score * faculty_score_settings.academic_score_weight / 100)
            + specialty_total
            + performance_total
        )
    else:
        # 如果没有学院成绩设置，使用默认权重80%
        calculated_score = (
            (academic_score * 80.0 / 100) + specialty_total + performance_total
        )

    # 更新综合成绩，保留四位小数
    student.comprehensive_score = round(calculated_score, 4)

    # 保存更改到数据库
    if commit:
        db.session.commit()

    return {
        "academic_specialty_total": student.academic_specialty_total,
        "comprehensive_performance_total": student.comprehensive_performance_total,
        "comprehensive_score": student.comprehensive_score,
    }


# 重新计算所有学生的综合成绩
@score_bp.route("/students/recalculate-comprehensive-scores", methods=["POST"])
def recalculate_comprehensive_scores():
    """
    重新计算所有学生的综合成绩
    仅允许管理员访问
    """
    from extensions import db
    from models import SystemSettings, Student, User, FacultyScoreSettings

    # 检查权限 - 仅管理员可以执行此操作
    username = request.args.get("username")
    if not username:
        return jsonify({"error": "缺少用户名参数"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or user.role != "admin":
        return jsonify({"error": "无权限执行此操作"}), 403

    try:
        # 获取所有学生
        students = Student.query.all()

        # 重新计算每个学生的综合成绩
        updated_count = 0
        for student in students:
            # 获取学生的学术专长总分和综合表现总分
            academic_score = student.academic_score or 0.0
            specialty_total = student.academic_specialty_total or 0.0
            performance_total = student.comprehensive_performance_total or 0.0

            # 获取学生所在学院的成绩设置
            faculty_score_settings = FacultyScoreSettings.query.filter_by(
                faculty_id=student.faculty_id
            ).first()

            # 应用满分限制
            if faculty_score_settings:
                specialty_total = min(
                    specialty_total, faculty_score_settings.specialty_max_score
                )
                performance_total = min(
                    performance_total, faculty_score_settings.performance_max_score
                )
            else:
                # 如果没有学院成绩设置，使用默认值
                specialty_total = min(specialty_total, 15.0)  # 默认学术专长满分15分
                performance_total = min(performance_total, 5.0)  # 默认综合表现满分5分

            # 计算综合成绩：学业成绩 * 学业成绩权重 / 100 + 学术专长总分 + 综合表现总分
            if faculty_score_settings:
                calculated_score = (
                    (
                        academic_score
                        * faculty_score_settings.academic_score_weight
                        / 100
                    )
                    + specialty_total
                    + performance_total
                )
            else:
                # 如果没有学院成绩设置，使用默认权重80%
                calculated_score = (
                    (academic_score * 80.0 / 100) + specialty_total + performance_total
                )

            # 同时更新数据库中的学术专长总分和综合表现总分，确保它们不超过满分
            student.academic_specialty_total = specialty_total
            student.comprehensive_performance_total = performance_total

            # 更新学生的综合成绩，保留四位小数
            student.comprehensive_score = round(calculated_score, 4)
            updated_count += 1

        # 保存所有更改到数据库
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "综合成绩重新计算完成",
                    "updated_students": updated_count,
                }
            ),
            200,
        )

    except Exception as e:
        # 发生错误时回滚事务
        db.session.rollback()
        current_app.logger.error(f"重新计算综合成绩时出错: {str(e)}")
        return jsonify({"error": "重新计算失败", "details": str(e)}), 500


# 获取学生推免成绩排名API
@score_bp.route("/students/ranking", methods=["GET"])
def get_students_ranking():
    try:
        # 获取查询参数
        faculty_id = request.args.get("facultyId")
        department_id = request.args.get("departmentId")
        major_id = request.args.get("majorId")

        # 构建查询条件 - 使用合并后的Student模型
        query = Student.query

        # 应用筛选条件 - 添加类型检查和转换
        if faculty_id and faculty_id != "all":
            try:
                faculty_id = int(faculty_id)
                query = query.filter_by(faculty_id=faculty_id)
            except ValueError:
                # 如果参数不是有效整数，忽略该筛选条件
                pass

        if department_id and department_id != "all":
            try:
                department_id = int(department_id)
                query = query.filter_by(department_id=department_id)
            except ValueError:
                # 如果参数不是有效整数，忽略该筛选条件
                pass

        if major_id and major_id != "all":
            try:
                major_id = int(major_id)
                query = query.filter_by(major_id=major_id)
            except ValueError:
                # 如果参数不是有效整数，忽略该筛选条件
                pass

        # 获取所有符合条件的学生数据
        students = query.all()

        # 按专业分组学生
        students_by_major = {}
        for student in students:
            major_id = student.major_id
            if major_id not in students_by_major:
                students_by_major[major_id] = []
            students_by_major[major_id].append(student)

        # 计算每个专业内学生的排名
        for major_id, major_students in students_by_major.items():
            # 按综合成绩降序排序
            major_students.sort(
                key=lambda s: s.comprehensive_score or 0.0, reverse=True
            )

            # 设置排名和总人数
            total_students = len(major_students)
            for i, student in enumerate(major_students):
                # 计算排名（处理并列情况）
                if (
                    i > 0
                    and student.comprehensive_score
                    == major_students[i - 1].comprehensive_score
                ):
                    student.major_ranking = major_students[i - 1].major_ranking
                else:
                    student.major_ranking = i + 1
                student.total_students = total_students

        from collections import defaultdict
        from material_models import MaterialRecord
        from workflow_models import ScoreEntry
        from use_cases.cycles import current_cycle_policy

        items = defaultdict(list)
        cycle = current_cycle_policy(required=False)
        if cycle and students:
            results = db.session.query(ScoreEntry, MaterialRecord).join(
                MaterialRecord, ScoreEntry.material_record_id == MaterialRecord.id
            ).filter(
                ScoreEntry.year == cycle.cycle_code, ScoreEntry.status == "active",
                ScoreEntry.student_id.in_([student.student_id for student in students]),
                MaterialRecord.student_id == ScoreEntry.student_id,
                MaterialRecord.faculty_id == ScoreEntry.faculty_id,
            ).order_by(ScoreEntry.id)
            for entry, record in results:
                facts = record.data or {}
                items[(entry.student_id, entry.score_group)].append({
                    "project_name": facts.get("project_name") or facts.get("competition_name") or facts.get("honor_name") or record.category,
                    "award_time": facts.get("award_date"),
                    "self_eval_score": None,
                    "score_basis": facts.get("description"),
                    "college_approved_score": float(entry.adjusted_score),
                    "total_score": float(entry.effective_score) if entry.included else 0,
                })

        # 按学生ID分组统计
        student_stats = {}

        # 从Student模型获取基本数据
        for student in students:
            student_id = student.id

            # 构建学生基本信息
            student_info = {
                "id": student.id,  # 添加主键ID字段
                "student_id": student.student_id,
                "student_name": student.student_name,
                "departmentId": student.department_id,
                "department": (
                    student.department.name if student.department else "未知系别"
                ),
                "majorId": student.major_id,
                "major": student.major.name if student.major else "未知专业",
                "facultyId": student.faculty_id,  # 添加学院ID
                "faculty": (
                    student.faculty.name if student.faculty else "未知学院"
                ),  # 添加学院名称，处理空值情况
                "gender": student.gender,
                "cet4_score": student.cet4_score,
                "cet6_score": student.cet6_score,
                "gpa": student.gpa,
                "academic_score": student.academic_score,
                "academic_specialty_total": student.academic_specialty_total or 0.0,
                "comprehensive_performance_total": student.comprehensive_performance_total
                or 0.0,
                # 保持向后兼容，total_score使用comprehensive_score的值
                "total_score": student.comprehensive_score or 0.0,
                "major_ranking": student.major_ranking,
                "major_total_students": student.total_students,
                "specialty_score": student.academic_specialty_total or 0.0,
                "comprehensive_score": student.comprehensive_score or 0.0,
                # 考核综合成绩总分（学术专长分 + 综合表现分）
                "total_comprehensive_score": (student.academic_specialty_total or 0.0)
                + (student.comprehensive_performance_total or 0.0),
                # 综合成绩（学业成绩*权重 + 学术专长分 + 综合表现分）
                "final_comprehensive_score": student.comprehensive_score or 0.0,
                # 向前端提供final_score字段，用于显示综合成绩
                "final_score": student.comprehensive_score or 0.0,
                "sequence": 0,
                # 添加加分项目信息
                "academicItems": items[(student.student_id, "academic")],
                "comprehensiveItems": items[(student.student_id, "comprehensive")],
            }

            student_stats[student_id] = student_info

        # 转换为列表并按最终综合成绩排序
        sorted_students = sorted(
            student_stats.values(), key=lambda x: x["final_score"], reverse=True
        )

        # 设置全局排名
        for i, student in enumerate(sorted_students):
            student["sequence"] = i + 1

        return (
            jsonify({"students": sorted_students, "total": len(sorted_students)}),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"获取学生排名时出错: {str(e)}")
        return jsonify({"error": "获取学生排名失败", "details": str(e)}), 500


# 获取所有学生信息接口
@score_bp.route("/students", methods=["GET"])
def get_all_students():
    # 获取请求参数
    search = request.args.get("search")
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    # 构建查询
    query = Student.query

    # 根据search关键词搜索
    if search:
        query = query.filter(
            (Student.student_name.like(f"%{search}%"))
            | (Student.student_id.like(f"%{search}%"))
        )

    # 分页查询
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    students = pagination.items

    student_list = []
    for student in students:
        # 获取学院、系和专业名称
        faculty_name = (
            Faculty.query.get(student.faculty_id).name if student.faculty_id else ""
        )
        department_name = (
            Department.query.get(student.department_id).name
            if student.department_id
            else ""
        )
        major_name = Major.query.get(student.major_id).name if student.major_id else ""

        student_data = {
            "id": student.id,
            "student_id": student.student_id,
            "student_name": student.student_name,
            "gender": student.gender,
            "faculty": faculty_name,
            "facultyId": student.faculty_id,
            "department": department_name,
            "departmentId": student.department_id,
            "major": major_name,
            "majorId": student.major_id,
            "cet4_score": student.cet4_score,
            "cet6_score": student.cet6_score,
            "gpa": student.gpa,
            "academic_score": student.academic_score,
            "academic_specialty_total": student.academic_specialty_total,
            "comprehensive_performance_total": student.comprehensive_performance_total,
            "total_score": student.comprehensive_score,  # 保持向后兼容，使用comprehensive_score的值
            "comprehensive_score": student.comprehensive_score,
            "major_ranking": student.major_ranking,
            "total_students": student.total_students,
        }
        student_list.append(student_data)

    # 返回分页数据
    return (
        jsonify(
            {
                "students": student_list,
                "total": pagination.total,
                "pages": pagination.pages,
                "current_page": pagination.page,
            }
        ),
        200,
    )


@score_bp.post("/students/academic-score-import/<mode>")
def import_academic_scores(mode):
    user = actor()
    if user.role != "admin" or not user.faculty_id:
        return jsonify({"error": "仅本学院管理员可导入学业成绩"}), 403
    if mode not in {"preview", "confirm"}:
        return jsonify({"error": "未知导入操作"}), 404
    try:
        rows, updates = plan_score_rows(read_score_rows(request.files.get("file")), user.faculty_id)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    digest = sha256(dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    approval = [user.id, user.faculty_id, digest]
    signer = URLSafeTimedSerializer(current_app.secret_key, salt="academic-score-import")
    if mode == "preview":
        return jsonify({"rows": rows, "ready_count": len(updates), "token": signer.dumps(approval)})

    conflict = {"error": "预览已过期或成绩已变化，请重新预览后确认", "code": "stale_preview"}
    try:
        approved = signer.loads(request.form.get("token", ""), max_age=1800)
    except BadData:
        return jsonify(conflict), 409
    if approved != approval:
        return jsonify(conflict), 409

    for student_id, previous, score in sorted(updates):
        changed = Student.query.filter_by(
            id=student_id, faculty_id=user.faculty_id, academic_score=previous
        ).update({Student.academic_score: score}, synchronize_session=False)
        if changed != 1:
            db.session.rollback()
            return jsonify(conflict), 409
    db.session.commit()
    return jsonify({"imported_count": len(updates), "skipped_count": len(rows) - len(updates)})


# 更新学生信息接口
@score_bp.route("/students/<int:student_id>", methods=["PUT"])
def update_student(student_id):
    student = Student.query.get(student_id)

    if not student:
        return jsonify({"message": "学生不存在"}), 404

    user = actor()
    if user.role != "admin" or not user.faculty_id or user.faculty_id != student.faculty_id:
        return jsonify({"error": "仅本学院管理员可更新学生基础资料", "code": "forbidden"}), 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "请求体必须为JSON对象", "code": "invalid_request"}), 400
    forbidden = sorted(DERIVED_STUDENT_FIELDS.intersection(data))
    if forbidden:
        return jsonify({
            "error": "派生计分与排名字段只能由权威计分或排名用例生成",
            "code": "derived_fields_read_only", "fields": forbidden,
        }), 400

    # 更新学生信息
    if "student_name" in data:
        student.student_name = data["student_name"]
    if "gender" in data:
        student.gender = data["gender"]
    if "facultyId" in data:
        student.faculty_id = data["facultyId"]
    if "department_id" in data:
        student.department_id = data["department_id"]
    if "major_id" in data:
        student.major_id = data["major_id"]
    if "cet4_score" in data:
        student.cet4_score = data["cet4_score"]
    if "cet6_score" in data:
        student.cet6_score = data["cet6_score"]
    if "gpa" in data:
        student.gpa = data["gpa"]
    if "academic_score" in data:
        student.academic_score = data["academic_score"]
    # academic_weighted字段已移除，由academic_score自动计算

    db.session.commit()

    return jsonify({"message": "学生信息更新成功"}), 200


# 获取学生加分统计
def _major_rank(student):
    """按综合分即时计算专业内排名与人数；只读，不写库。

    历史实现会在 GET 里重算并 commit 全专业排名：1000 人规模下首个请求约 1.3 秒，
    并发访问时还会抢 SQLite 写锁。权威排名在 RankingBatch 与计分快照里，
    这里只需要一个展示用的即时结果。

    并列名次沿用「严格高于我的人数 + 1」，与原先按排序位置赋值的结果一致：
    [10, 5, 5, 3] → 1, 2, 2, 4。
    """
    if not student.major_id:
        return "-", 0
    mine = student.comprehensive_score or 0.0
    total = db.session.query(func.count(Student.id)).filter(
        Student.major_id == student.major_id
    ).scalar() or 0
    ahead = db.session.query(func.count(Student.id)).filter(
        Student.major_id == student.major_id,
        func.coalesce(Student.comprehensive_score, 0.0) > mine,
    ).scalar() or 0
    return ahead + 1, total


@score_bp.route("/students/statistics", methods=["GET"])
def get_student_statistics():
    # 获取查询参数
    student_id = request.args.get("studentId")
    if not student_id:
        return jsonify({"error": "缺少学生ID参数"}), 400

    # 首先查询Student模型获取统计数据
    student = Student.query.filter_by(student_id=student_id).first()

    if student:
        # 从Student模型获取统计数据
        academic_score = student.academic_score or 0.0
        gpa = student.gpa or 0.0
        specialty_score = student.academic_specialty_total or 0.0
        performance_total = student.comprehensive_performance_total or 0.0
        comprehensive_score = student.comprehensive_score or 0.0
        # 保持向后兼容，total_score使用comprehensive_score的值
        total_score = comprehensive_score

        # 排名与专业人数改为只读即时计算，GET 不再写库。
        ranking, major_total_students = _major_rank(student)
    else:
        # 如果Student模型中没有数据，初始化默认值
        academic_score = 0.0
        gpa = 0.0
        specialty_score = 0.0
        performance_total = 0.0
        comprehensive_score = 0.0
        # 保持向后兼容，total_score使用comprehensive_score的值
        total_score = 0.0
        ranking = "-"
        major_total_students = 0

    from material_models import MaterialRecord
    approved_count = MaterialRecord.query.filter(
        MaterialRecord.student_id == student_id,
        MaterialRecord.status.in_(("scored", "verified", "verified_not_eligible")),
    ).count()

    # 构建响应数据
    # 注意：这里使用下划线命名以匹配前端期望的格式
    statistics_data = {
        "student_id": student_id,
        "total_score": round(total_score, 2),
        "academic_score": round(academic_score, 2),
        "gpa": round(gpa, 2),
        "specialty_score": round(specialty_score, 2),
        "comprehensive_performance_total": round(performance_total, 2),
        "comprehensive_score": round(comprehensive_score, 2),
        "ranking": ranking,
        "major_total_students": major_total_students,
        "approved_count": approved_count,
        "faculty_id": student.faculty_id if student else None,
    }

    return jsonify(statistics_data), 200
