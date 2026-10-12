from models import Rule, RuleCalculation
from extensions import db
import json


class RuleEngine:
    """
    规则引擎核心类，用于处理推免综合成绩计算的规则匹配与分值计算
    """

    def __init__(self):
        # 计算类型映射表
        self.calculation_types = {
            "tree": "树结构计算",
        }

    def match_and_calculate(self, rules, student_data):
        """
        匹配规则并计算分数

        参数:
        - rules: 规则列表
        - student_data: 学生数据字典

        返回:
        - 包含匹配规则和总得分的结果字典
        """
        matched_rules = []
        total_score = 0.0
        matched_details = []

        # 遍历所有规则
        for rule in rules:
            # 创建临时对象用于条件评估
            class TempApplication:
                def __init__(self, data):
                    self.__dict__ = data

            application = TempApplication(student_data)
            student = TempApplication(student_data)

            # 直接匹配规则并计算分数
            score = self.calculate_score(rule, student_data)
            matched_rules.append(rule)
            total_score += score
            matched_details.append(
                {
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "rule_type": rule.type,
                    "score": score,
                }
            )

        return {
            "matched_rules_count": len(matched_rules),
            "total_score": total_score,
            "matched_rules": matched_details,
        }

    def calculate_score(self, rule, student_data):
        """
        计算单个规则的分数
        :param rule: Rule对象或规则ID
        :param student_data: 学生数据（字典或对象）
        :return: 计算得到的分数
        """
        try:
            # 如果传入的是规则ID，获取Rule对象
            if isinstance(rule, int):
                from models import Rule

                rule = Rule.query.get(rule)
                if not rule:
                    print(f"规则ID {rule} 不存在")
                    return 0.0

            if not rule:
                return 0.0

            # 获取规则的计算配置（通过relationship访问）
            calculation = rule.calculation
            if not calculation:
                return 0.0

            # 仅支持树结构计算类型
            if calculation.calculation_type == "tree":
                # 对于树结构计算，我们将student_data作为application参数传递
                score = self._calculate_tree_score(calculation, student_data)
                return score
            else:
                return 0.0
        except Exception as e:
            return 0.0

    def _calculate_tree_score(self, calculation, student_data):
        """
        树结构计算得分
        """
        if not calculation.parameters:
            return 0.0

        try:
            # 处理参数：如果已经是字典则直接使用，否则解析JSON字符串
            if isinstance(calculation.parameters, dict):
                params = calculation.parameters
            else:
                params = json.loads(calculation.parameters)
                if not isinstance(params, dict):
                    return 0.0

            # 获取树结构配置（从tree.structure路径获取）
            tree_config = params.get("tree", {}).get("structure", {})
            if not tree_config:
                return 0.0

            # 转换student_data为字典格式
            student_dict = {}
            if hasattr(student_data, "__dict__"):
                student_dict = {
                    k: v
                    for k, v in student_data.__dict__.items()
                    if not k.startswith("_")
                }
            elif isinstance(student_data, dict):
                student_dict = student_data
            else:
                return 0.0

            # 提取树路径
            tree_path = student_dict.get("tree_path", [])

            if not tree_path or not isinstance(tree_path, list):
                return 0.0

            # 查找匹配路径的分数
            def find_node_score(node, path_index=0):
                if not node:
                    return 0.0
                if path_index >= len(tree_path):
                    return 0.0

                # 获取节点名称（从dimension.name中获取）
                node_name = node.get("dimension", {}).get("name", "")
                expected_name = tree_path[path_index]
                # 忽略空格进行比较
                node_name_stripped = node_name.replace(" ", "")
                expected_name_stripped = expected_name.replace(" ", "")

                # 检查当前节点是否匹配路径中的当前项（忽略空格）
                if node_name_stripped == expected_name_stripped:
                    # 如果是最后一个路径项，返回该节点的分数
                    if path_index == len(tree_path) - 1:
                        node_score = float(node.get("score", 0.0))
                        return node_score
                    # 否则继续向下查找所有子节点，找到最深层的匹配节点
                    max_score = 0.0
                    for child in node.get("children", []):
                        score = find_node_score(child, path_index + 1)
                        if score > max_score:
                            max_score = score
                    if max_score > 0:
                        return max_score

                # 没有找到匹配的路径
                return 0.0

            # 从根节点的子节点开始匹配路径
            found = False
            result = 0.0

            # 获取根节点
            root_node = tree_config.get("root", {})

            # 遍历根节点的所有子节点
            for child in root_node.get("children", []):
                # 从根节点的子节点开始匹配路径
                score = find_node_score(child, 0)
                if score > 0:
                    result = score
                    found = True
                    break

            if not found:
                result = 0.0

            # 应用最大值限制
            if calculation.max_score is not None:
                result = min(result, float(calculation.max_score))

            return round(result, 4)
        except Exception as e:
            return 0.0


# 创建规则引擎实例
rule_engine = RuleEngine()
