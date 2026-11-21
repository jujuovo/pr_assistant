"""信息学院办法第6–7页及第10页。"""
from decimal import Decimal

POLICY_VERSION = "info-innovation-2025-02"
SCORES = {
    "national": {"leader": Decimal("1"), "member": Decimal("0.3")},
    "provincial": {"leader": Decimal("0.5"), "member": Decimal("0.2")},
    "university": {"leader": Decimal("0.1"), "member": Decimal("0.05")},
}


def candidate(category, facts, cutoff):
    if not facts["completed"]:
        return Decimal(0), "项目尚未结题"
    if facts["completion_date"] > cutoff:
        return Decimal(0), "结项时间超过截止日"
    return SCORES[facts["level"]][facts["role"]], "已核验结项证明、立项级别和角色"


def allocate_innovation(entries):
    seen = set()
    remaining = Decimal(2)
    for entry in sorted(entries, key=lambda item: (-item.candidate_score, item.material_record_id)):
        identity = entry.exclusion_basis["project_key"]
        score = entry.candidate_score
        reason = None
        if not score:
            reason = entry.exclusion_basis["basis"]
        elif identity in seen:
            score = 0
            reason = "同一项目多次认定，仅计最高分"
        else:
            seen.add(identity)
            if score > remaining:
                score = remaining
                reason = "创新创业训练累计上限2分"
            remaining -= score
        entry.effective_score = score
        entry.included = bool(score)
        entry.exclusion_reason = reason
