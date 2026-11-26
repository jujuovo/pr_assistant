"""OCR facts, student confirmations, private originals and reviewed snapshots stay separate."""
import copy
import importlib.util
import io
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from PIL import Image
from sqlalchemy import inspect

from conftest import login
from extensions import db
from material_models import MaterialRecord, MaterialAttachment
from legacy_models import Application
from models import Student, User
from ocr_models import OCRJob, OCRMaterialLink
from services.competition_ocr.jobs import job_root
from services.competition_ocr.mapping import suggestions, raw_suggestions
from services.materials.service import stored_path

AWARD = {"event": "测试竞赛", "edition": "第十届", "participants": ["张三", "李四"],
         "project": "测试作品", "school": "测试大学", "award": "二等奖", "group": "普通教育组",
         "stage_as_printed": "全国总决赛", "certificate_no": "CERT-123", "advisers": ["王五"],
         "award_date": "2026年5月8日"}
LANQIAO = {"school": "测试大学", "student": "张三", "teacher": "王五", "edition": "第十届",
           "track": "C/C++程序设计", "group": "大学A组", "region": "福建赛区", "award": "二等奖",
           "certificate_no": "1234567890", "date": "2026年5月8日"}
CSP = {"document_type": "csp_transcript", "name": "张三", "certificate_no": "CCF-IDEN-CSP-2025-98765",
       "test_date": "2025.09.21", "batch": "39", "language": "C++", "test_site": "测试大学",
       "task_scores": [100, 100, 40, 0, 20], "total_score": 260}
CASES = [
    ("lanqiao", LANQIAO, "competition"),
    *((key, AWARD, "competition") for key in ("computer-design", "challenge-cup")),
    ("software-design", AWARD, "competition_evidence"),
    ("csp", CSP, "certification"),
    ("social-practice", {"document_type": "practice_proof", "team": "测试实践队", "period_as_printed": "2025年暑假",
                         "issuer": "学校", "members": ["张三"], "issue_date": "2025-09-01"}, "social_practice"),
    ("social-practice", {"document_type": "team_list", "teams": ["甲实践队", "乙实践队"]}, "social_practice"),
    ("social-practice", {"document_type": "platform_screenshot", "submitter": "张三", "honor_name": "优秀个人",
                         "practice": "暑期实践", "honor_description": "实践表彰", "honor_date": "2025年10月1日",
                         "review_status_as_printed": "待学院审核"}, "social_practice"),
    ("other", {"document_type": "appointment_proof", "name": "张三", "organization": "学生会", "position": "部长",
               "start_month": "2025年9月", "end_month": "2026年9月"}, "student_work"),
    ("other", {"document_type": "research_report", "report_no": "R-123", "requester_school": "测试大学",
               "database": "Web of Science", "publication_year": "2025"}, "research"),
]


def completed_data(key, fields):
    mapped = suggestions(key, {"fields": fields})
    data = copy.deepcopy(mapped["data"])
    if mapped["material_category"] == "competition":
        data.update(project_name=data.get("project_name") or "测试项目", level="national",
                    award=data.get("award") or "second", event_year=2026, participation_mode="individual")
    elif key == "csp":
        data["full_score"] = 500
    elif mapped["material_category"] == "student_work":
        data["as_of"] = "2026-11-19"
        data["appointments"][0].update(position_level="院级", start_date="2025-09-01",
                                       end_date="2026-09-30", assessment_result="优秀")
    return data


def prepared_job(env, key="csp", fields=None):
    if key in {"lanqiao", "computer-design", "challenge-cup"}:
        from test_ocr_workflow_integration import setup_formal
        setup_formal(env)
    login(env[1], env[2]["student"])
    image = io.BytesIO()
    Image.new("RGB", (600, 600), "white").save(image, format="PNG")
    payload = image.getvalue()
    response = env[1].post(f"/api/ocr/{key}/recognize", data={"file": (io.BytesIO(payload), "sample.png")})
    assert response.status_code == 202, response.json
    job = db.session.get(OCRJob, response.json["id"])
    job.status = "manual_review"
    job.report = {"category": key, "fields": copy.deepcopy(CSP if fields is None else fields),
                  "source_sha256": job.sha256, "images": {"original": "input.png"},
                  "authenticity": "not_assessed", "requires_human_verification": True}
    db.session.commit()
    return job.id, payload


def confirm_url(job_id):
    return f"/api/ocr/jobs/{job_id}/confirm-material"


@pytest.mark.parametrize("key,fields,target", CASES)
def test_every_adapter_maps_confirms_and_preserves_raw_facts(env, key, fields, target):
    job_id, original = prepared_job(env, key, fields)
    report = copy.deepcopy(db.session.get(OCRJob, job_id).report)
    preview = env[1].get(f"/api/ocr/jobs/{job_id}").json
    mapping = preview["mapping"]
    assert mapping["material_category"] == target
    assert env[1].get(f"/api/ocr/jobs/{job_id}/mapping").json["mapping"] == mapping
    response = env[1].post(confirm_url(job_id), json={"year": 2028 if target == "competition" else 2026, "data": completed_data(key, fields)})
    assert response.status_code == 201, response.json
    material = response.json["material"]
    assert material["category"] == target and material["status"] == "draft"
    assert material["analysis"]["ocr_executed"] is True and material["bonus_result"] is None
    assert material["recognition_status"] == "confirmed" and len(material["ocr_links"]) == 1
    assert material["ocr_links"][0]["suggestions"] == mapping
    assert material["ocr_links"][0]["confirmed_snapshot"] == material["data"]
    assert env[1].get(material["attachments"][0]["url"]).data == original
    assert db.session.get(OCRJob, job_id).report == report
    poll = env[1].get(preview["result_url"]).json
    assert poll["material_record_id"] == material["id"] and poll["application_id"] is None
    assert env[1].get(poll["material_url"]).json["data"] == material["data"]
    assert env[1].post(confirm_url(job_id), json={"year": 2028 if target == "competition" else 2026, "data": completed_data(key, fields)}).status_code == 409
    assert MaterialRecord.query.count() == MaterialAttachment.query.count() == OCRMaterialLink.query.count() == 1
    assert Application.query.count() == 0
    assert Student.query.filter_by(student_id="S1").one().academic_score == 80


def test_missing_fields_dates_and_months_are_not_guessed():
    mapped = raw_suggestions("computer-design", {"fields": AWARD})
    assert mapped["data"]["award_date"] == "2026-05-08"
    assert mapped["missing_fields"] == ["organizer", "competition_level"]
    assert "competition_level" not in mapped["data"]
    missing_date = {**LANQIAO, "date": "2026年5月"}
    assert "award_date" in raw_suggestions("lanqiao", {"fields": missing_date})["missing_fields"]
    mapped = raw_suggestions("csp", {"fields": {**CSP, "total_score": 0, "task_scores": [0]*5}})
    assert mapped["data"]["score"] == 0 and mapped["missing_fields"] == ["full_score"]
    appointment = raw_suggestions("other", {"fields": CASES[-2][1]})
    assert appointment["data"]["appointments"][0]["start_date"] is None
    assert appointment["data"]["start_month_as_printed"] == "2025年9月"
    assert appointment["data"]["subject_name"] == "张三"
    assert raw_suggestions("other", {"fields": {"document_type": None}})["material_category"] is None


@pytest.mark.parametrize("bad", ["missing", "too_high", "nan", "wrong_sum", "invalid_date", "unknown_field"])
def test_invalid_confirmation_rolls_back_without_material(env, bad):
    job_id, _ = prepared_job(env)
    data = completed_data("csp", CSP)
    if bad == "missing": del data["full_score"]
    if bad == "too_high": data["full_score"] = 100
    if bad == "nan": data["score"] = "NaN"
    if bad == "wrong_sum": data["task_scores"] = [0]*5
    if bad == "invalid_date": data["test_date"] = "2025-02-30"
    if bad == "unknown_field": data["bonus_score"] = 10
    response = env[1].post(confirm_url(job_id), json={"year": 2026, "data": data})
    assert response.status_code == 400, response.json
    assert MaterialRecord.query.count() == OCRMaterialLink.query.count() == MaterialAttachment.query.count() == 0


@pytest.mark.parametrize("failure", ["queued", "failed", "unknown_type", "tampered", "missing_original"])
def test_unready_or_changed_original_cannot_be_confirmed(env, failure):
    job_id, _ = prepared_job(env)
    job = db.session.get(OCRJob, job_id)
    if failure in ("queued", "failed"): job.status = failure
    elif failure == "unknown_type": job.category, job.report = "other", {"fields": {"document_type": None}}
    elif failure == "tampered": (job_root(job_id) / "input.png").write_bytes(b"changed")
    else: (job_root(job_id) / "input.png").unlink()
    db.session.commit()
    response = env[1].post(confirm_url(job_id), json={"year": 2026, "data": completed_data("csp", CSP)})
    assert response.status_code == 409, response.json
    assert MaterialRecord.query.count() == OCRMaterialLink.query.count() == 0


def test_confirmation_authorization_and_read_access(env):
    job_id, _ = prepared_job(env)
    owner = db.session.get(User, env[2]["student"])
    peer = User(username="peer", name="同院学生", password="x", role="student", status="active", faculty_id=owner.faculty_id)
    db.session.add(peer)
    db.session.commit()
    for user in (peer.id, env[2]["other"], env[2]["admin"]):
        login(env[1], user)
        assert env[1].post(confirm_url(job_id), json={"year": 2026, "data": completed_data("csp", CSP)}).status_code == 403
    login(env[1], peer.id)
    assert env[1].get(f"/api/ocr/jobs/{job_id}/mapping").status_code == 403
    assert MaterialRecord.query.count() == 0


def test_student_corrections_and_teacher_review_preserve_two_snapshots(env):
    job_id, _ = prepared_job(env)
    data = completed_data("csp", CSP)
    data.update(score=270, task_scores=[100,100,50,0,20])
    row = env[1].post(confirm_url(job_id), json={"year": 2026, "data": data}).json["material"]
    path = f"/api/materials/certification/records/{row['id']}"
    assert row["data"]["score"] == "270"
    assert row["ocr_links"][0]["suggestions"]["data"]["score"] == 260
    changed = {**row["data"], "subject_name": "学生后来修正姓名"}
    updated = env[1].patch(path, json={"version": row["version"], "data": changed})
    assert updated.status_code == 200
    assert updated.json["analysis"]["ocr_executed"] is True
    assert updated.json["ocr_links"][0]["confirmed_snapshot"]["subject_name"] == "张三"
    submitted = env[1].post(path+"/submit", json={"version": updated.json["version"]}).json
    login(env[1], env[2]["admin"])
    assert env[1].get(path).json["ocr_links"][0]["job_id"] == job_id
    reviewed = env[1].post(path+"/review", json={"version": submitted["version"], "decision": "verified", "comment": "已核对"})
    assert reviewed.status_code == 200, reviewed.json
    audit = env[1].get(path+"/events").json["events"][-1]["details"]
    assert audit["data_snapshot"]["subject_name"] == "学生后来修正姓名"
    assert audit["ocr_links_snapshot"][0]["confirmed_snapshot"]["subject_name"] == "张三"
    assert audit["attachments_snapshot"][0]["sha256"] == db.session.get(OCRJob, job_id).sha256
    assert db.session.get(OCRJob, job_id).report["fields"]["total_score"] == 260


def test_linking_existing_record_checks_version_and_reuses_attachment(env):
    job_id, original = prepared_job(env)
    row = env[1].post('/api/materials/certification/records', json={"year": 2026, "data": completed_data("csp", CSP)}).json
    path = f"/api/materials/certification/records/{row['id']}"
    row = env[1].post(path+"/attachments", data={"version": "1", "files": (io.BytesIO(original), "same.png")}).json
    body = {"material_record_id": row["id"], "version": 1, "data": row["data"]}
    assert env[1].post(confirm_url(job_id), json=body).status_code == 409
    body["version"] = row["version"]
    response = env[1].post(confirm_url(job_id), json=body)
    assert response.status_code == 200, response.json
    assert response.json["material"]["version"] == 3
    assert MaterialAttachment.query.count() == 1
    assert OCRMaterialLink.query.one().material_record_id == row["id"]


def test_recognize_material_attachment_queues_without_auto_confirmation(env):
    _, original = prepared_job(env)
    row = env[1].post('/api/materials/certification/records', json={"year": 2026, "data": completed_data("csp", CSP)}).json
    path = f"/api/materials/certification/records/{row['id']}"
    row = env[1].post(path+"/attachments", data={"version": "1", "files": (io.BytesIO(original), "sample.png")}).json
    body = {"version": row["version"], "attachment_id": row["attachments"][0]["id"], "project_key": "csp"}
    response = env[1].post(path+"/recognize", json=body)
    assert response.status_code == 202 and response.json["status"] == "queued"
    assert OCRMaterialLink.query.count() == 0
    assert env[1].post(path+"/recognize", json={**body, "version": 1}).status_code == 409
    assert env[1].post(path+"/recognize", json={**body, "project_key": "lanqiao"}).status_code == 400
    attachment = MaterialAttachment.query.one()
    stored_path(attachment.stored_name).write_bytes(b"tampered")
    assert env[1].post(path+"/recognize", json=body).status_code == 409


@pytest.mark.parametrize("state", ["draft", "pending", "other_owner", "other_faculty"])
def test_ocr_confirmation_rejects_all_legacy_application_links(env, state):
    job_id, _ = prepared_job(env)
    student = Student.query.filter_by(student_id="S1").one()
    application = Application(student_id="S1", student_name="张三", faculty_id=student.faculty_id,
        department_id=student.department_id, major_id=student.major_id, application_type="academic",
        project_name="待关联申请", status="draft", self_score=2)
    if state == "pending": application.status = "pending"
    if state == "other_faculty": application.faculty_id = db.session.get(User, env[2]["other"]).faculty_id
    if state == "other_owner":
        db.session.add(Student(student_id="S2", student_name="李四", faculty_id=student.faculty_id,
                               department_id=student.department_id, major_id=student.major_id))
        application.student_id = "S2"
    db.session.add(application)
    db.session.commit()
    response = env[1].post(confirm_url(job_id), json={"year": 2026, "application_id": application.id, "data": completed_data("csp", CSP)})
    assert response.status_code == 409, response.json
    assert response.json["code"] == "material_route_required"
    assert MaterialRecord.query.count() == OCRMaterialLink.query.count() == 0
    db.session.refresh(application)
    assert application.self_score == 2 and application.final_score is None


def test_write_failure_removes_new_attachment_and_rolls_back(env, monkeypatch):
    job_id, _ = prepared_job(env)
    from services.competition_ocr import binding
    def fail(*args): raise ValueError("模拟保存失败")
    monkeypatch.setattr(binding, "event", fail)
    response = env[1].post(confirm_url(job_id), json={"year": 2026, "data": completed_data("csp", CSP)})
    assert response.status_code == 400
    assert MaterialRecord.query.count() == OCRMaterialLink.query.count() == MaterialAttachment.query.count() == 0
    assert not list(Path(env[0].config["MATERIAL_STORAGE_FOLDER"]).glob("*"))


def test_link_migration_matches_model_and_reverses(env):
    path = Path(__file__).parents[1]/"migrations/versions/20261118_ocr_material_links.py"
    spec = importlib.util.spec_from_file_location("ocr_links_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    db.session.remove()
    OCRMaterialLink.__table__.drop(db.engine)
    with db.engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert {c["name"] for c in inspect(connection).get_columns("ocr_material_link")} == set(OCRMaterialLink.__table__.columns.keys())
            assert inspect(connection).get_pk_constraint("ocr_material_link")["constrained_columns"] == ["job_id"]
            module.downgrade()
            assert not inspect(connection).has_table("ocr_material_link")
            module.upgrade()


def test_confirm_refuses_tampered_existing_attachment(env):
    job_id, original = prepared_job(env)
    row = env[1].post('/api/materials/certification/records', json={"year": 2026, "data": completed_data("csp", CSP)}).json
    path = f"/api/materials/certification/records/{row['id']}"
    row = env[1].post(path+"/attachments", data={"version": "1", "files": (io.BytesIO(original), "sample.png")}).json
    attachment = MaterialAttachment.query.one()
    stored_path(attachment.stored_name).write_bytes(b"tampered")
    response = env[1].post(confirm_url(job_id), json={"material_record_id": row["id"], "version": row["version"], "data": row["data"]})
    assert response.status_code == 409, response.json
    assert OCRMaterialLink.query.count() == 0
    assert env[1].get(path).json["version"] == row["version"]


@pytest.mark.parametrize("change", [{"document_type": "bad"}, {"teams": []}, {"teams": "队名"}, {"teams": [None]}])
def test_social_subtype_and_array_validation(env, change):
    job_id, _ = prepared_job(env, "social-practice", {"document_type": "team_list", "teams": ["测试队"]})
    data = {"document_type": "team_list", "teams": ["测试队"], **change}
    response = env[1].post(confirm_url(job_id), json={"year": 2026, "data": data})
    assert response.status_code == 400
    assert MaterialRecord.query.count() == OCRMaterialLink.query.count() == 0


def test_submitted_record_cannot_receive_new_ocr_confirmation(env):
    job_id, _ = prepared_job(env)
    row = env[1].post('/api/materials/certification/records', json={"year": 2026, "data": completed_data("csp", CSP)}).json
    path = f"/api/materials/certification/records/{row['id']}"
    submitted = env[1].post(path+"/submit", json={"version": row["version"]}).json
    response = env[1].post(confirm_url(job_id), json={"material_record_id": row["id"], "version": submitted["version"], "data": row["data"]})
    assert response.status_code == 409
    assert OCRMaterialLink.query.count() == 0 and MaterialAttachment.query.count() == 0


def test_openapi_new_category_examples_validate_against_business_schema(env):
    from services.materials.schemas import normalize
    login(env[1], env[2]["student"])
    spec = env[1].get('/api/materials/openapi.json').json
    examples = spec['paths']['/api/materials/{category}/records']['post']['requestBody']['content']['application/json']['examples']
    for category in ('certification', 'social_practice', 'research', 'arts_sports'):
        assert normalize(category, examples[category]['value']['data'])
