from use_cases.deprecation import LEGACY_CONSUMERS, legacy_exit_gate


def test_legacy_exit_gate_blocks_until_every_condition_is_clear():
    blocked = legacy_exit_gate(consumer_counts={name: 1 for name in LEGACY_CONSUMERS},
        reconciliation_differences=1, consecutive_clean_runs=1, backup_verified=False,
        automation_regressions_passed=False)
    assert not blocked["can_remove_legacy_data"]
    assert {x["code"] for x in blocked["blockers"]} == {
        "active_consumers", "reconciliation_differences",
        "insufficient_clean_runs", "backup_not_verified",
        "automation_regressions_not_verified"}
    clear = legacy_exit_gate(consumer_counts={name: 0 for name in LEGACY_CONSUMERS},
        reconciliation_differences=0, consecutive_clean_runs=2, backup_verified=True,
        automation_regressions_passed=True)
    assert clear == {"can_remove_legacy_data": True, "blockers": []}


def test_legacy_fields_and_compatibility_endpoints_remain_present():
    from pathlib import Path
    from models import Application, Student

    assert "final_score" in Application.__table__.c
    assert {"academic_specialty_total", "comprehensive_performance_total",
            "comprehensive_score"} <= set(Student.__table__.c.keys())
    root = Path(__file__).resolve().parents[2]
    assert '@application_bp.route("/applications"' in (
        root / "backend/blueprints/application_bp.py").read_text(encoding="utf-8")
    assert '@score_bp.route("/students/statistics"' in (
        root / "backend/blueprints/score_bp.py").read_text(encoding="utf-8")
