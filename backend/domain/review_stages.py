"""Shared role and stage policy for the three-stage material review workflow.

This policy is introduced separately from endpoint integration so callers can
adopt it without changing scoring rules or rewriting historical decisions.
"""

REVIEWER_ROLES = frozenset({"reviewer_level1", "reviewer_level2"})
REVIEW_ROLES = REVIEWER_ROLES | {"teacher", "admin"}
ACCOUNT_ROLES = REVIEW_ROLES | {"student"}
ROLE_LABELS = {
    "student": "学生", "teacher": "教师", "admin": "管理员",
    "reviewer_level1": "一级审核员", "reviewer_level2": "二级审核员",
}
ROLE_STAGES = {"reviewer_level1": 1, "reviewer_level2": 2, "teacher": 3}
STAGE_LABELS = {1: "一级审核", 2: "二级审核", 3: "教师终审"}


def can_review_stage(role, actor_faculty_id, material_faculty_id, stage):
    """Administrators can intervene within their existing faculty boundary."""
    if actor_faculty_id is None or actor_faculty_id != material_faculty_id:
        return False
    if type(stage) is not int or stage not in STAGE_LABELS:
        return False
    return role == "admin" or ROLE_STAGES.get(role) == stage


def next_review_stage(stage):
    if type(stage) is not int or stage not in STAGE_LABELS:
        raise ValueError("无效审核阶段")
    return stage + 1 if stage < 3 else None
