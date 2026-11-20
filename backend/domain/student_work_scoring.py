"""信息学院2025年2月办法第9–10页，学生干部任职。"""
from decimal import Decimal

POLICY_VERSION = "info-student-work-2025-02"
POSITIONS = {
    Decimal("2"): ("院学生会执行主席", "团总支书记"),
    Decimal("1.5"): ("院学生会主席团成员", "团总支副书记"),
    Decimal("1"): ("院学生会各部部长", "团总支各部部长", "党支部书记", "班长", "团支部书记"),
    Decimal("0.75"): ("系团总支书记", "院学生会各部门副部长", "团总支各部门副部长", "社团社长"),
    Decimal("0.5"): ("党支部委员", "系团总支各部部长", "各班班委", "团支部委员", "院学生会长期志愿者",
                     "团总支长期志愿者", "社团副社长", "社团主要干部", "辩论队队长", "球队队长"),
}
COEFFICIENT = {position: coefficient for coefficient, positions in POSITIONS.items() for position in positions}
TENURE = {"below_semester": Decimal(0), "semester": Decimal("0.5"), "full_year": Decimal(1)}


def candidate(category, facts, cutoff):
    details = []
    for row in facts["assessments"]:
        coefficient = COEFFICIENT[row["mapped_position"]]
        score = coefficient * Decimal(row["assessment_score"]) / 100 * TENURE[row["tenure"]]
        reason = ""
        if row["proof_date"] > cutoff:
            score, reason = Decimal(0), "证明落款超过截止日"
        elif row["tenure"] == "below_semester":
            reason = "任期不足一学期"
        elif not score:
            reason = "核定考核分为0"
        details.append(dict(row, coefficient=str(coefficient), candidate=str(score), reason=reason))
    return sum(Decimal(row["candidate"]) for row in details), details


def allocate(entries):
    ordered = sorted(((entry, dict(row)) for entry in entries for row in entry.exclusion_basis["basis"]),
                     key=lambda pair: (pair[1]["academic_year"], -Decimal(pair[1]["candidate"]),
                                       pair[0].material_record_id, pair[1]["appointment_index"]))
    seen = set()
    remaining = Decimal(2)
    allocations = {entry.id: [] for entry in entries}
    for entry, row in ordered:
        year = row["academic_year"]
        score = Decimal(row["candidate"])
        if score and year in seen:
            score, row["reason"] = Decimal(0), "同学年只计最高职务得分"
        if score:
            seen.add(year)
            if score > remaining:
                score, row["reason"] = remaining, "学生干部累计上限2分"
            remaining -= score
        allocations[entry.id].append(dict(row, included_score=str(score)))
    for entry in entries:
        rows = allocations[entry.id]
        entry.effective_score = sum(Decimal(row["included_score"]) for row in rows)
        entry.included = bool(entry.effective_score)
        entry.exclusion_basis = dict(entry.exclusion_basis, allocations=rows)
        entry.exclusion_reason = "；".join(dict.fromkeys(row["reason"] for row in rows if row["reason"])) or None
