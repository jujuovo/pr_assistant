"""旧 Application 写入闸门：已迁移类别不得再从旧入口新建申请。

对应文档：docs/legacy-application-exit.md
"""
import pytest

from conftest import login
from extensions import db
from legacy_models import Application
from blueprints.application_bp import MIGRATED_MATERIAL_ROUTES


def post_application(client, ids, **overrides):
    payload = {"studentId": "S1", "facultyId": 1, "departmentId": 1, "majorId": 1,
               "name": "张三", "projectName": "测试项目", "selfScore": 1}
    payload.update(overrides)
    return client.post("/api/applications", json=payload)


@pytest.mark.parametrize("application_type", sorted(MIGRATED_MATERIAL_ROUTES))
def test_migrated_category_cannot_create_legacy_application(env, application_type):
    app, client, ids = env
    login(client, ids["student"])

    response = post_application(client, ids, applicationType=application_type)

    assert response.status_code == 409, response.json
    assert response.json["code"] == MIGRATED_MATERIAL_ROUTES[application_type]["code"]
    assert response.json["route"] == MIGRATED_MATERIAL_ROUTES[application_type]["route"]
    # 闸门必须在写库之前，不能留下半条记录
    assert Application.query.count() == 0


def test_guard_also_matches_underscore_field_name(env):
    """前端可能直接送下划线字段，守卫两种写法都要拦住。"""
    app, client, ids = env
    login(client, ids["student"])
    response = post_application(client, ids, **{"application_type": "student_work"})
    assert response.status_code == 409
    assert response.json["code"] == "student_work_material_route_required"
    assert Application.query.count() == 0


def test_unmigrated_category_still_uses_legacy_chain(env):
    """学业成绩等尚未迁移的类别必须保持可用，否则兼容链路会被误伤。"""
    app, client, ids = env
    login(client, ids["student"])
    response = post_application(client, ids, applicationType="academic")
    blocked_codes = {item["code"] for item in MIGRATED_MATERIAL_ROUTES.values()}
    assert response.json.get("code") not in blocked_codes


def test_history_read_is_not_blocked(env):
    """只堵写入，历史查询必须继续可读，否则教师审核历史会一起断。"""
    app, client, ids = env
    login(client, ids["teacher"] if "teacher" in ids else ids["other"])
    response = client.get("/api/applications")
    assert response.status_code == 200


def test_certificate_assessment_fk_is_restrict_not_cascade():
    """证书评估是审核依据，不能被删除旧申请时静默级联清掉。

    原先是 ondelete=CASCADE：删一条 application 会连带删除评估记录且不留痕，
    事后无法恢复；改成 RESTRICT 后由数据库把冲突暴露出来。
    """
    from certificate_models import CertificateAssessment

    fk = next(iter(CertificateAssessment.__table__.c.application_id.foreign_keys))
    assert fk.ondelete == "RESTRICT"


@pytest.mark.parametrize("field", ["applicationType", "application_type", "sub_type"])
def test_invention_patent_requires_new_material_route_without_rule_id(env, field):
    _, client, ids = env
    login(client, ids["student"])
    response = post_application(client, ids, **{field: "invention_patent"})
    assert response.status_code == 409
    assert response.json["code"] == "invention_patent_material_route_required"
    assert response.json["route"] == "/api/materials/invention_patent/records"
    assert Application.query.count() == 0
