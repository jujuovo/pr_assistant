# -*- coding: utf-8 -*-
"""
规则管理蓝图

该文件负责处理规则管理相关的API端点，包括：
- 获取所有规则
- 获取单个规则
- 创建规则
- 更新规则
- 删除规则
- 切换规则状态（启用/禁用）
- 根据申请信息匹配规则
"""

from flask import Blueprint, request, jsonify
from models import Rule, RuleCalculation, Application
from extensions import db
import traceback
import json
from utils.rule_engine import RuleEngine
import sys

# 设置默认编码为UTF-8
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 创建蓝图实例
rule_bp = Blueprint("rule", __name__, url_prefix="/api")


# 获取所有规则
@rule_bp.route("/rules", methods=["GET"])
def get_rules():
    # 获取查询参数
    rule_type = request.args.get("type")
    status = request.args.get("status")
    level = request.args.get("level")
    name = request.args.get("name")
    faculty_id = request.args.get("faculty_id")

    # 构建查询
    query = Rule.query

    if rule_type:
        query = query.filter_by(type=rule_type)

    if status:
        query = query.filter_by(status=status)

    if name:
        query = query.filter(Rule.name.like(f"%{name}%"))

    if faculty_id:
        query = query.filter(
            (Rule.faculty_id == faculty_id) | (Rule.faculty_id.is_(None))
        )

    rules = query.all()
    rule_list = []

    for rule in rules:
        rule_data = {
            "id": rule.id,
            "name": rule.name,
            "type": rule.type,
            "sub_type": rule.sub_type,
            "research_type": rule.research_type,
            "score": rule.score,
            "max_score": rule.max_score,
            "max_count": rule.max_count,
            "status": rule.status,
            "description": rule.description,
            "faculty_id": rule.faculty_id,
            "faculty_name": rule.faculty.name if rule.faculty else None,
            "calculation_formula": rule.calculation_formula,
            "createdAt": rule.created_at.isoformat() if rule.created_at else None,
            "updatedAt": rule.updated_at.isoformat() if rule.updated_at else None,
        }
        rule_list.append(rule_data)

    return jsonify({"rules": rule_list}), 200


# 获取单个规则
@rule_bp.route("/rules/<int:rule_id>", methods=["GET"])
def get_rule(rule_id):
    try:
        rule = Rule.query.get(rule_id)
        if not rule:
            return jsonify({"code": 404, "message": "Rule not found"}), 404

        # 规则条件功能已移除
        condition_list = []

        # 获取该规则的计算
        calculation = RuleCalculation.query.filter_by(rule_id=rule_id).first()
        calculation_data = None
        if calculation:
            calculation_data = {
                "id": calculation.id,
                "rule_id": calculation.rule_id,
                "calculation_type": calculation.calculation_type,
                "formula": calculation.formula,
                "parameters": calculation.parameters,
                "max_score": calculation.max_score,
            }

        rule_data = {
            "id": rule.id,
            "name": rule.name,
            "type": rule.type,
            "sub_type": rule.sub_type,
            "research_type": rule.research_type,
            "score": rule.score,
            "max_score": rule.max_score,
            "max_count": rule.max_count,
            "status": rule.status,
            "description": rule.description,
            "faculty_id": rule.faculty_id,
            "faculty_name": rule.faculty.name if rule.faculty else None,
            "calculation_formula": rule.calculation_formula,
            "conditions": condition_list,
            "calculation": calculation_data,
            "createdAt": rule.created_at.isoformat() if rule.created_at else None,
            "updatedAt": rule.updated_at.isoformat() if rule.updated_at else None,
        }

        return jsonify({"code": 200, "message": "Success", "data": rule_data}), 200
    except Exception as e:
        return jsonify({"code": 500, "message": str(e)}), 500


# 创建规则
@rule_bp.route("/rules", methods=["POST"])
def create_rule():
    try:
        data = request.get_json()
        print(f"Received data for creating rule: {data}")

        # 验证必填字段
        required_fields = ["name", "type", "score"]
        for field in required_fields:
            if field not in data:
                print(f"Missing required field: {field}")
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # 处理JSON字段，确保它们是有效的JSON对象

        calculation_formula = data.get("calculation_formula")
        if isinstance(calculation_formula, str):
            try:
                calculation_formula = json.loads(calculation_formula)
            except json.JSONDecodeError:
                calculation_formula = None

        # 创建新规则
        new_rule = Rule(
            name=data["name"],
            type=data["type"],
            sub_type=data.get("sub_type"),
            research_type=data.get("research_type"),
            score=data["score"],
            max_score=data.get("max_score"),
            max_count=data.get("max_count"),
            status=data.get("status", "active"),
            description=data.get("description"),
            faculty_id=data.get("faculty_id"),
            calculation_formula=calculation_formula,
        )

        db.session.add(new_rule)
        print("Added new rule to session")
        db.session.commit()
        print("Committed new rule to database")

        # 处理规则计算
        calculation_data = data.get("calculation")
        if calculation_data:
            # 验证parameters是否为有效的JSON对象
            parameters = calculation_data.get("parameters")
            if parameters is not None:
                if isinstance(parameters, str):
                    try:
                        parameters = json.loads(parameters)
                    except json.JSONDecodeError:
                        return (
                            jsonify({"error": "Invalid JSON format for parameters"}),
                            400,
                        )
                elif not isinstance(parameters, dict):
                    return (
                        jsonify({"error": "Parameters must be a valid JSON object"}),
                        400,
                    )

            new_calculation = RuleCalculation(
                rule_id=new_rule.id,
                calculation_type=calculation_data.get("calculation_type"),
                formula=calculation_data.get("formula"),
                parameters=parameters,
                max_score=calculation_data.get("max_score"),
            )
            db.session.add(new_calculation)

        db.session.commit()

        return (
            jsonify(
                {
                    "id": new_rule.id,
                    "name": new_rule.name,
                    "type": new_rule.type,
                    "sub_type": new_rule.sub_type,
                    "research_type": new_rule.research_type,
                    "score": new_rule.score,
                    "max_score": new_rule.max_score,
                    "max_count": new_rule.max_count,
                    "status": new_rule.status,
                    "description": new_rule.description,
                    "createdAt": (
                        new_rule.created_at.isoformat() if new_rule.created_at else None
                    ),
                    "updatedAt": (
                        new_rule.updated_at.isoformat() if new_rule.updated_at else None
                    ),
                }
            ),
            201,
        )

    except Exception as e:
        print(f"Error creating rule: {type(e).__name__}: {e}")
        traceback.print_exc()
        return (
            jsonify({"error": f"Failed to create rule: {type(e).__name__}: {e}"}),
            500,
        )


# 更新规则
@rule_bp.route("/rules/<int:rule_id>", methods=["PUT"])
def update_rule(rule_id):
    try:
        rule = Rule.query.get_or_404(rule_id)
        data = request.get_json()

        # 更新规则字段
        if "name" in data:
            rule.name = data["name"]
        if "type" in data:
            rule.type = data["type"]
        if "sub_type" in data:
            rule.sub_type = data["sub_type"]
        if "research_type" in data:
            rule.research_type = data["research_type"]
        if "score" in data:
            rule.score = data["score"]
        if "max_score" in data:
            rule.max_score = data["max_score"]
        if "max_count" in data:
            rule.max_count = data["max_count"]

        if "status" in data:
            rule.status = data["status"]
        if "description" in data:
            rule.description = data["description"]
        if "faculty_id" in data:
            rule.faculty_id = data["faculty_id"]

        if "calculation_formula" in data:
            calculation_formula = data["calculation_formula"]
            if isinstance(calculation_formula, str):
                try:
                    calculation_formula = json.loads(calculation_formula)
                except json.JSONDecodeError:
                    calculation_formula = None
            rule.calculation_formula = calculation_formula

        db.session.commit()

        # 更新规则计算
        calculation_data = data.get("calculation")
        if calculation_data is not None:
            # 删除旧的计算
            RuleCalculation.query.filter_by(rule_id=rule_id).delete()
            # 添加新的计算
            if calculation_data:
                # 验证parameters是否为有效的JSON对象
                parameters = calculation_data.get("parameters")
                if parameters is not None:
                    if isinstance(parameters, str):
                        try:
                            parameters = json.loads(parameters)
                        except json.JSONDecodeError:
                            return (
                                jsonify(
                                    {"error": "Invalid JSON format for parameters"}
                                ),
                                400,
                            )
                    elif not isinstance(parameters, dict):
                        return (
                            jsonify(
                                {"error": "Parameters must be a valid JSON object"}
                            ),
                            400,
                        )

                new_calculation = RuleCalculation(
                    rule_id=rule_id,
                    calculation_type=calculation_data.get("calculation_type"),
                    formula=calculation_data.get("formula"),
                    parameters=parameters,
                    max_score=calculation_data.get("max_score"),
                )
                db.session.add(new_calculation)

        db.session.commit()

        return (
            jsonify(
                {
                    "id": rule.id,
                    "name": rule.name,
                    "type": rule.type,
                    "sub_type": rule.sub_type,
                    "research_type": rule.research_type,
                    "score": rule.score,
                    "max_score": rule.max_score,
                    "max_count": rule.max_count,
                    "status": rule.status,
                    "description": rule.description,
                    "faculty_id": rule.faculty_id,
                    "calculation_formula": rule.calculation_formula,
                    "createdAt": (
                        rule.created_at.isoformat() if rule.created_at else None
                    ),
                    "updatedAt": (
                        rule.updated_at.isoformat() if rule.updated_at else None
                    ),
                    "message": "Rule updated successfully",
                }
            ),
            200,
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400


# 删除规则
@rule_bp.route("/rules/<int:rule_id>", methods=["DELETE"])
def delete_rule(rule_id):
    try:
        rule = Rule.query.get_or_404(rule_id)

        # 删除所有引用该规则的申请记录
        Application.query.filter_by(rule_id=rule_id).update({"rule_id": None})

        # 删除规则
        db.session.delete(rule)
        db.session.commit()

        return jsonify({"message": "Rule deleted successfully"}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Failed to delete rule"}), 500


# 批量删除规则
@rule_bp.route("/rules/batch-delete", methods=["POST"])
def batch_delete_rules():
    try:
        data = request.get_json()
        rule_ids = data.get("ids", [])

        if not rule_ids or not isinstance(rule_ids, list):
            return jsonify({"error": "Invalid or empty rule IDs"}), 400

        # 删除所有引用这些规则的申请记录
        Application.query.filter(Application.rule_id.in_(rule_ids)).update(
            {"rule_id": None}, synchronize_session=False
        )

        # 先删除关联的规则计算记录
        RuleCalculation.query.filter(RuleCalculation.rule_id.in_(rule_ids)).delete(
            synchronize_session=False
        )

        # 然后删除规则
        Rule.query.filter(Rule.id.in_(rule_ids)).delete(synchronize_session=False)
        db.session.commit()

        return jsonify({"message": "Rules deleted successfully"}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Failed to delete rules"}), 500


# RuleCalculation API endpoints
@rule_bp.route("/rules/<int:rule_id>/calculation", methods=["GET"])
def get_rule_calculation(rule_id):
    try:
        # 检查规则是否存在
        rule = Rule.query.get_or_404(rule_id)

        # 获取规则的计算信息
        calculation = RuleCalculation.query.filter_by(rule_id=rule_id).first()
        calculation_data = None
        if calculation:
            calculation_data = {
                "id": calculation.id,
                "rule_id": calculation.rule_id,
                "calculation_type": calculation.calculation_type,
                "formula": calculation.formula,
                "parameters": calculation.parameters,
                "max_score": calculation.max_score,
            }

        return (
            jsonify({"code": 200, "message": "Success", "data": calculation_data}),
            200,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"code": 500, "message": str(e)}), 500


@rule_bp.route("/rules/<int:rule_id>/calculation", methods=["POST"])
def create_calculation(rule_id):
    try:
        # 检查规则是否存在
        rule = Rule.query.get_or_404(rule_id)

        data = request.get_json()

        # 检查是否已存在计算，一个规则只能有一个计算
        existing_calculation = RuleCalculation.query.filter_by(rule_id=rule_id).first()
        if existing_calculation:
            return (
                jsonify(
                    {
                        "code": 400,
                        "message": "A calculation already exists for this rule",
                    }
                ),
                400,
            )

        new_calculation = RuleCalculation(
            rule_id=rule_id,
            calculation_type=data.get("calculation_type"),
            formula=data.get("formula"),
            parameters=data.get("parameters"),
            max_score=data.get("max_score"),
        )

        db.session.add(new_calculation)
        db.session.commit()

        return (
            jsonify(
                {
                    "code": 201,
                    "message": "Calculation created successfully",
                    "data": {
                        "id": new_calculation.id,
                        "rule_id": new_calculation.rule_id,
                        "calculation_type": new_calculation.calculation_type,
                        "formula": new_calculation.formula,
                        "parameters": new_calculation.parameters,
                        "max_score": new_calculation.max_score,
                    },
                }
            ),
            201,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"code": 500, "message": str(e)}), 500


@rule_bp.route("/calculations/<int:calculation_id>", methods=["PUT"])
def update_calculation(calculation_id):
    try:
        calculation = RuleCalculation.query.get_or_404(calculation_id)
        data = request.get_json()

        # 更新计算信息
        calculation.calculation_type = data.get(
            "calculation_type", calculation.calculation_type
        )
        calculation.formula = data.get("formula", calculation.formula)
        calculation.parameters = data.get("parameters", calculation.parameters)
        calculation.max_score = data.get("max_score", calculation.max_score)

        db.session.commit()

        return (
            jsonify(
                {
                    "code": 200,
                    "message": "Calculation updated successfully",
                    "data": {
                        "id": calculation.id,
                        "rule_id": calculation.rule_id,
                        "calculation_type": calculation.calculation_type,
                        "formula": calculation.formula,
                        "parameters": calculation.parameters,
                        "max_score": calculation.max_score,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"code": 500, "message": str(e)}), 500


@rule_bp.route("/calculations/<int:calculation_id>", methods=["DELETE"])
def delete_calculation(calculation_id):
    try:
        calculation = RuleCalculation.query.get_or_404(calculation_id)
        db.session.delete(calculation)
        db.session.commit()

        return (
            jsonify({"code": 200, "message": "Calculation deleted successfully"}),
            200,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"code": 500, "message": str(e)}), 500


@rule_bp.route("/rules/match", methods=["POST"])
def match_rules():
    try:
        data = request.get_json()

        # 获取学生数据和学院ID
        student_data = data.get("student_data")
        faculty_id = data.get("faculty_id")

        if not student_data:
            return jsonify({"code": 400, "message": "Student data is required"}), 400

        # 初始化规则引擎
        rule_engine = RuleEngine()

        # 获取该学院的所有有效规则
        rules = Rule.query.filter_by(faculty_id=faculty_id, status="active").all()

        # 匹配规则并计算分数
        result = rule_engine.match_and_calculate(rules, student_data)

        return jsonify({"code": 200, "message": "Success", "data": result}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"code": 500, "message": str(e)}), 500


@rule_bp.route("/rules/<int:rule_id>/calculate", methods=["POST"])
def calculate_rule_score(rule_id):
    try:
        data = request.get_json()
        student_data = data.get("student_data")

        if not student_data:
            return jsonify({"code": 400, "message": "Student data is required"}), 400

        # 获取规则 - 使用get而不是get_or_404，避免返回HTML错误页面
        rule = Rule.query.get(rule_id)
        if not rule:
            return jsonify({"code": 404, "message": "Rule not found"}), 404

        # 调试信息
        print(f"[DEBUG] API调用: rule_id={rule_id}, student_data={student_data}")
        print(f"[DEBUG] Rule对象: id={rule.id}, name={rule.name}")

        # 初始化规则引擎
        rule_engine = RuleEngine()

        # 计算单个规则的分数
        # 注意：这里直接传递字典而不是对象，因为calculate_score方法已经支持处理字典
        score = rule_engine.calculate_score(rule, student_data)

        # 调试信息
        print(f"[DEBUG] 计算结果: score={score}")

        # 获取RuleCalculation对象以获取max_score
        from models import RuleCalculation

        calculation = RuleCalculation.query.filter_by(rule_id=rule.id).first()
        max_score = calculation.max_score if calculation else None

        return (
            jsonify(
                {
                    "code": 200,
                    "message": "Success",
                    "data": {
                        "rule_id": rule_id,
                        "rule_name": rule.name,
                        "score": score,
                        "max_score": max_score,
                    },
                }
            ),
            200,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"code": 500, "message": str(e)}), 500


@rule_bp.route("/rules/<int:rule_id>/status", methods=["PATCH"])
def toggle_rule_status(rule_id):
    try:
        rule = Rule.query.get_or_404(rule_id)
        rule.status = "active" if rule.status == "disabled" else "disabled"
        db.session.commit()

        return (
            jsonify(
                {
                    "id": rule.id,
                    "status": rule.status,
                    "message": f"Rule status updated to {rule.status}",
                }
            ),
            200,
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400
