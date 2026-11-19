from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_inventory_records_roles_authority_and_compatibility_boundary():
    text = (ROOT / "docs/role-workflow-inventory.md").read_text(encoding="utf-8")
    for role in ("## 学生", "## 教师", "## 管理员"):
        assert role in text
    for authority in ("MaterialRecord", "CompetitionRulePackage", "ScoreEntry", "Application"):
        assert authority in text
    assert "compatibility only" in text
    assert "交叉写入评审结论" in text


def test_competition_and_legacy_frontends_do_not_cross_import_write_clients():
    student_competition = (ROOT / "frontend/src/pages/student/applications/CompetitionWorkflow.vue").read_text(encoding="utf-8")
    teacher_competition = (ROOT / "frontend/src/pages/teacher/reviews/TeacherCompetitionReview.vue").read_text(encoding="utf-8")
    legacy_form = (ROOT / "frontend/src/pages/student/applications/ApplicationForm.vue").read_text(encoding="utf-8")

    for source in (student_competition, teacher_competition):
        assert "materialApi" in source
        assert "createApplication" not in source
        assert "updateApplication" not in source
        assert "getRules" not in source
    assert "@/services/materialApi.js" not in legacy_form
    assert "applicationsStore.addApplication" in legacy_form
