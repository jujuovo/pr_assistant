from conftest import approve_pending_preliminaries
from material_models import MaterialRecord
from datetime import date
from io import BytesIO
import json

from conftest import login
from extensions import db
from domain.innovation_scoring import POLICY_VERSION
from models import Rule, Student, User
from domain.research_scoring import POLICY_VERSION as RESEARCH_VERSION
import pytest
from use_cases.cycles import activate_cycle_policy, create_cycle_policy
from use_cases.rule_versions import publish_rule_version
from workflow_models import ScoreEntry, StudentScoreSnapshot


@pytest.mark.parametrize("reverse", [False, True])
def test_innovation_api(env, reverse):
    _, client, users = env
    admin = db.session.get(User, users["admin"])
    teacher = User(username="research_teacher", name="教师", role="teacher", status="active",
                   password="test", faculty_id=admin.faculty_id)
    db.session.add(teacher)
    policy, _ = create_cycle_policy(admin, 2028, date(2025, 9, 1), date(2028, 8, 31), "2028")
    activate_cycle_policy(admin, policy)
    rule = Rule(name="大创", type="academic", sub_type="innovation", score=0,
                faculty_id=admin.faculty_id, status="active", calculation_formula={"policy_id": POLICY_VERSION})
    db.session.add(rule)
    publish_rule_version(rule, published_by=admin, cycle_code=2028)
    patent = Rule(name="专利", type="academic", sub_type="research", research_type="patent",
                  score=0, faculty_id=admin.faculty_id, status="active",
                  calculation_formula={"policy_id": RESEARCH_VERSION})
    db.session.add(patent)
    publish_rule_version(patent, published_by=admin, cycle_code=2028)
    Student.query.filter_by(student_id="S1").one().academic_score = 90
    db.session.commit()

    def review(category, facts):
        login(client, users["student"])
        base = "/api/materials/" + category + "/records"
        created = client.post(base, data={"year": "2028", "data": json.dumps({k: v for k, v in facts.items() if k not in {"project_key", "identity_basis"}}),
                              "files": (BytesIO(b"%PDF-1.4\nproof"), "proof.pdf")})
        assert created.status_code == 201, created.json
        row = created.json
        url = base + "/" + str(row["id"])
        submitted = client.post(url + "/submit", json={"version": row["version"]})
        assert submitted.status_code == 200, submitted.json
        assert client.post(url + "/submit", json={"version": row["version"]}).status_code >= 400
        approve_pending_preliminaries(client)
        login(client, teacher.id)
        payload = dict(version=db.session.get(MaterialRecord, submitted.json["id"]).version, decision="verified", comment="核对原件",
                       idempotency_key="verify", verified_facts=facts)
        accepted = client.post(url + "/review", json=payload)
        assert accepted.status_code == 200, accepted.json
        assert client.post(url + "/review", json=payload).json["replayed"]
        return accepted.json

    category = "innovation_training"
    facts = dict(project_name="同名项目", project_number="N42", level="national", role="leader",
                 completed=True, completion_date="2028-08-31", proof_type="academic_affairs",
                 project_key="A", identity_basis="教务处结题证明列明两级立项编号")
    levels = ["national", "provincial"] if reverse else ["provincial", "national"]
    for level in levels:
        result = review(category, facts | dict(level=level))
        if level == "national":
            high = result
    current = lambda: StudentScoreSnapshot.query.filter_by(status="current").one()
    assert current().specialty_score == 1
    login(client, users["student"])
    url = "/api/materials/innovation_training/records/" + str(high["record_id"])
    declared = {k: v for k, v in facts.items() if k not in {"project_key", "identity_basis"}}
    corrected = client.post(url + "/corrections", json={"version": high["version"],
                            "confirmed_terms": declared})
    assert corrected.status_code == 201, corrected.json
    entry = db.session.get(ScoreEntry, high["scoring"]["score_entry_id"])
    successor = "/api/materials/innovation_training/records/" + str(corrected.json["id"])
    uploaded = client.post(successor + "/attachments", data={"version": str(corrected.json["version"]),
                           "files": (BytesIO(b"%PDF-1.4\ncorrected"), "corrected.pdf")})
    assert uploaded.status_code in (200, 201), uploaded.json
    submitted = client.post(successor + "/submit", json={"version": uploaded.json["version"]})
    assert submitted.status_code == 200 and entry.status == "active"
    approve_pending_preliminaries(client)
    login(client, teacher.id)
    accepted = client.post(successor + "/review", json=dict(version=db.session.get(MaterialRecord, submitted.json["id"]).version,
                           decision="verified", comment="新原件落款超期", idempotency_key="correction",
                           verified_facts=facts | dict(completion_date="2028-09-01")))
    assert accepted.status_code == 200, accepted.json
    assert entry.status == "invalidated"
    assert current().specialty_score == 0.5 and current().comprehensive_score == 72.5
    for key in "ABC":
        review(category, facts | dict(project_key=key))
    review(category, facts | dict(completed=False))
    assert current().specialty_score == 2 and current().comprehensive_score == 74
    login(client, users["student"])
    explanation = client.get("/api/workflow/students/S1/score/current").json
    reasons = [item["exclusion_reason"] or "" for item in explanation["entries"]]
    for fragment in ["上限", "同一项目", "超过截止日", "尚未结题"]:
        assert any(fragment in reason for reason in reasons)
    print("innovation audit", high, "correction", accepted.json, "snapshot", current().id,
          current().rule_version_ids, current().comprehensive_score)
    for index in range(7):
        review("invention_patent", dict(title="专利", work_key=f"CN{index}", first_institution="厦门大学",
               authors=["甲"], student_author="甲", authorized_national_invention=True,
               certificate_date="2028-08-31"))
    login(client, users["student"])
    explanation = client.get("/api/workflow/students/S1/score/current").json
    assert current().specialty_raw_score == 16 and current().specialty_score == 15
    assert explanation["comprehensive_score"] == "87.0000"
