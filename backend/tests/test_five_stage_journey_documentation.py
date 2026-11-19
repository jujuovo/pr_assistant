from pathlib import Path


def test_five_stage_manual_journey_documents_roles_states_and_no_side_effects():
    text = (Path(__file__).parents[2] / "docs/structured-scoring-five-stage-journey.md").read_text(encoding="utf-8")
    for phrase in (
        "学生保存无规则材料", "管理员补充规则", "学生重新确认",
        "教师只核验正式提交材料", "学生查看权威结果",
        "rule_unmatched", "rule_available", "材料词条没有对应计分",
        "没有对应 `ScoreEntry`", "尚无权威计分快照", "未运行真实 OCR",
    ):
        assert phrase in text
