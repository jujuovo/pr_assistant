from datetime import date
from io import BytesIO
import json
from conftest import login
from domain.student_work_scoring import POLICY_VERSION
from extensions import db
from models import Faculty, Rule, Student, User
from test_student_work_scoring import assessment
from use_cases.cycles import activate_cycle_policy, create_cycle_policy
from use_cases.rule_versions import publish_rule_version
from workflow_models import ScoreEntry, StudentScoreSnapshot


def test_student_work_review(env):
    _, client, users = env
    admin = db.session.get(User, users["admin"])
    db.session.get(Faculty, admin.faculty_id).name = "信息学院"
    teacher = User(username="work_teacher", name="教师", role="teacher", status="active",
                   password="test", faculty_id=admin.faculty_id)
    db.session.add(teacher)
    policy, _ = create_cycle_policy(admin, 2028, date(2025,9,1), date(2028,8,31), "2028")
    activate_cycle_policy(admin, policy)
    rule = Rule(name="干部", type="comprehensive", sub_type="student_work", score=0,
                faculty_id=admin.faculty_id, status="active", calculation_formula={"policy_id":POLICY_VERSION})
    db.session.add(rule)
    publish_rule_version(rule, published_by=admin, cycle_code=2028)
    Student.query.filter_by(student_id="S1").one().academic_score = 90
    db.session.commit()
    base = "/api/materials/student_work/records"
    current = lambda: StudentScoreSnapshot.query.filter_by(status="current").one()
    for fact, expected in [(assessment(), 1.2), (assessment(mapped_position="院学生会执行主席", assessment_score=45), 1.2),
                           (assessment(mapped_position="班长", academic_year=2026, assessment_score=100), 2)]:
        login(client, users["student"])
        data = dict(as_of="2028-08-31", appointments=[dict(organization="学院", position=fact["mapped_position"],
                    position_level="院", start_date=f'{fact["academic_year"]}-09-01', end_date=None, assessment_result="自评100")])
        created = client.post(base, data=dict(year="2028", data=json.dumps(data),
                              files=(BytesIO(b"%PDF-1.4\nproof"), "proof.pdf")))
        assert created.status_code == 201, created.json
        url = base + "/" + str(created.json["id"])
        submitted = client.post(url+"/submit", json=dict(version=created.json["version"]))
        assert submitted.status_code == 200, submitted.json
        login(client, teacher.id)
        command = dict(decision="verified", version=submitted.json["version"], idempotency_key="accept",
                       comment="核对岗位、学年、考核表", verified_facts={"assessments":[fact]})
        incomplete = dict(fact)
        incomplete.pop("assessment_score")
        invalid = client.post(url+"/review", json=command | {"verified_facts":{"assessments":[incomplete]}})
        assert invalid.status_code == 400 and "assessment_score" in str(invalid.json)
        response = client.post(url+"/review", json=command)
        assert response.status_code == 200, response.json
        assert client.post(url+"/review", json=command).json["replayed"]
        assert float(current().performance_score) == expected
        if fact["mapped_position"] == "院学生会主席团成员":
            highest = url, data, response.json
        print("work audit", response.json, current().comprehensive_score)
    login(client, users["student"])
    explanation = client.get("/api/workflow/students/S1/score/current").json
    assert explanation["comprehensive_score"] == "74.0000"
    assert all(item["score_group"] == "comprehensive" for item in explanation["entries"])
    assert any("上限" in (item["exclusion_reason"] or "") for item in explanation["entries"])
    detail = client.get(base+"/3").json["bonus_result"]
    assert float(detail["candidate_score"]) == 1 and float(detail["included_score"]) == 0.8
    assert detail["details"][0]["assessment_source"] == "签章考核表"
    url, data, high = highest
    corrected = client.post(url+"/corrections", json=dict(version=high["version"], confirmed_terms=data))
    assert corrected.status_code == 201, corrected.json
    successor = base+"/"+str(corrected.json["id"])
    uploaded = client.post(successor+"/attachments", data=dict(version=str(corrected.json["version"]),
                           files=(BytesIO(b"%PDF-1.4\nnew"), "new.pdf")))
    submitted = client.post(successor+"/submit", json=dict(version=uploaded.json["version"]))
    login(client, teacher.id)
    rejected = client.post(successor+"/review", json=dict(version=submitted.json["version"], decision="rejected",
                           idempotency_key="reject", comment="原最高项证明撤销"))
    assert rejected.status_code == 200, rejected.json
    assert db.session.get(ScoreEntry, high["scoring"]["score_entry_id"]).status == "invalidated"
    assert float(current().comprehensive_score) == 73.9
    from test_volunteer_material_ocr import upload, Provider, run_one_ocr, refresh, submit, path
    volunteer = upload(env, hours="240")
    assert run_one_ocr(env[0], Provider(hours="240"))
    submitted = submit(env, refresh(env, volunteer))
    assert submitted.status_code == 200, submitted.json
    login(client, teacher.id)
    result = client.post(path(volunteer)+"/review", json=dict(version=submitted.json["version"],
                         decision="verified", comment="核对240普通工时", idempotency_key="volunteer"))
    assert result.status_code == 200, result.json
    assert float(current().performance_score) == 2.9
    assert float(current().comprehensive_score) == 74.9
    print("volunteer", volunteer["id"], "snapshot", current().id, current().rule_version_ids,
          current().comprehensive_score)

    # A historical fixture represents an existing adjudication without an attributable academic year.
    # All new student-work scores above and below run through the authenticated review command.
    login(client, users["student"])
    created = client.post(base, data=dict(year="2028", data=json.dumps(data),
                          files=(BytesIO(b"%PDF-1.4\nannual"), "annual.pdf")))
    url = base + "/" + str(created.json["id"])
    submitted = client.post(url+"/submit", json=dict(version=created.json["version"]))
    login(client, teacher.id)
    historical = ScoreEntry(student_id="S1", faculty_id=admin.faculty_id, year=2028, category="student_work",
        score_group="comprehensive", source_type="legacy_application", source_id="old-17", source_revision=1,
        rule_version_id=db.session.get(ScoreEntry, high["scoring"]["score_entry_id"]).rule_version_id, raw_score=1, adjusted_score=1, effective_score=1,
        status="active", included=True, idempotency_key="old-17")
    db.session.add(historical)
    db.session.commit()
    multi = dict(version=submitted.json["version"], decision="verified", comment="分别核对两学年",
                 idempotency_key="annual", verified_facts={"assessments":[assessment(),
                 assessment(academic_year=2026, assessment_score=90, assessment_source="第二学年签章考核表")]})
    blocked = client.post(url+"/review", json=multi)
    assert blocked.status_code == 409 and "old-17" in str(blocked.json)
    assert float(current().comprehensive_score) == 74.9
    assert historical.status == "active"
