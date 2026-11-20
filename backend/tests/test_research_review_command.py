from datetime import date
from io import BytesIO
import json

from conftest import login
from extensions import db
from domain.research_scoring import POLICY_VERSION
from models import Rule, User
from test_research_scoring import PAPER
from use_cases.cycles import activate_cycle_policy, create_cycle_policy
from use_cases.rule_versions import publish_rule_version
from workflow_models import ScoreEntry, StudentScoreSnapshot


def test_research_api(env):
    _, client, users = env
    admin = db.session.get(User, users["admin"])
    teacher = User(username="research_teacher", name="教师", role="teacher", status="active",
                   password="test", faculty_id=admin.faculty_id)
    db.session.add(teacher)
    policy, _ = create_cycle_policy(admin, 2028, date(2025, 9, 1), date(2028, 8, 31), "2028")
    activate_cycle_policy(admin, policy)
    for kind in ("thesis", "patent"):
        rule = Rule(name=kind, type="academic", sub_type="research", research_type=kind, score=1,
                    faculty_id=admin.faculty_id, status="active", calculation_formula={"policy_id": POLICY_VERSION})
        db.session.add(rule)
        publish_rule_version(rule, published_by=admin, cycle_code=2028)
    db.session.commit()

    def review(category, facts):
        login(client, users["student"])
        base = "/api/materials/" + category + "/records"
        created = client.post(base, data={"year": "2028", "data": json.dumps(facts),
                              "files": (BytesIO(b"%PDF-1.4\nproof"), "proof.pdf")})
        assert created.status_code == 201, created.json
        row = created.json
        url = base + "/" + str(row["id"])
        submitted = client.post(url + "/submit", json={"version": row["version"]})
        assert submitted.status_code == 200, submitted.json
        login(client, teacher.id)
        payload = dict(version=submitted.json["version"], decision="verified", comment="核对原件",
                       idempotency_key="verify", verified_facts=facts)
        accepted = client.post(url + "/review", json=payload)
        assert accepted.status_code == 200, accepted.json
        assert client.post(url + "/review", json=payload).json["replayed"]
        return accepted.json

    for index in range(3):
        review("research_paper", PAPER | dict(work_key=str(index), ccf_grade="C"))
    current = lambda: StudentScoreSnapshot.query.filter_by(status="current").one()
    assert current().specialty_score == 2
    result = review("research_paper", PAPER | dict(venue="Nature"))
    entry = db.session.get(ScoreEntry, result["scoring"]["score_entry_id"])
    assert entry.candidate_score == 20 and entry.rule_version_id in current().rule_version_ids
    assert current().specialty_score == 15 and current().comprehensive_score == 79
    facts = dict(title="专利", work_key="CN123", first_institution="厦门大学", authors=["甲"],
                 student_author="甲", authorized_national_invention=True, certificate_date="2028-08-31")
    review("invention_patent", facts)
    review("invention_patent", facts)
    assert ScoreEntry.query.filter_by(category="invention_patent", included=True).count() == 1
    assert current().specialty_raw_score == 24
    login(client, users["student"])
    explanation = client.get("/api/workflow/students/S1/score/current")
    assert explanation.status_code == 200
    assert explanation.json["comprehensive_score"] == str(current().comprehensive_score)
    group = explanation.json["categories"]["academic"]
    assert group["raw_score"] == "24.0000" and group["effective_score"] == "15.0000"
    assert "上限" in group["note"]
    assert any(item["item_bonus"] == "20.0000" for item in explanation.json["entries"])
    excluded = [item for item in explanation.json["entries"] if item["exclusion_reason"]]
    assert any(item["candidate_score"] == "1.0000" and item["included_score"] == "0"
               and "两篇" in item["exclusion_reason"] for item in excluded)
    url = "/api/materials/research_paper/records/" + str(result["record_id"])
    corrected = client.post(url + "/corrections", json={"version": result["version"],
                            "confirmed_terms": PAPER | dict(venue="Nature")})
    assert corrected.status_code == 201, corrected.json
    assert entry.status == "active" and current().specialty_raw_score == 24
    successor = "/api/materials/research_paper/records/" + str(corrected.json["id"])
    uploaded = client.post(successor + "/attachments", data={"version": str(corrected.json["version"]),
                           "files": (BytesIO(b"%PDF-1.4\ncorrected"), "corrected.pdf")})
    assert uploaded.status_code in (200, 201), uploaded.json
    submitted = client.post(successor + "/submit", json={"version": uploaded.json["version"]})
    assert submitted.status_code == 200 and entry.status == "active"
    login(client, teacher.id)
    accepted = client.post(successor + "/review", json=dict(version=submitted.json["version"],
                           decision="verified", comment="新原件落款超期", idempotency_key="correction",
                           verified_facts=PAPER | dict(venue="Nature", proof_date="2028-09-02")))
    assert accepted.status_code == 200, accepted.json
    assert entry.status == "invalidated"
    assert current().specialty_score == 4 and current().comprehensive_score == 68
    print("research audit", result, accepted.json, "final", current().id, current().comprehensive_score)
