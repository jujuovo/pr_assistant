import io
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from PIL import Image
import pytest
from conftest import login
from extensions import db
from models import Application, Student
from automation_models import AutomationBatch, AutomationItem, AutomationReview
from services.recognition.worker import run_one


def image_bytes(color="white"):
    output = io.BytesIO()
    Image.new("RGB", (1000, 1500), color).save(output, format="PNG")
    return output.getvalue()


def credit(hours="+5.05", day="21", end="17:36:34"):
    texts = ["信用时数详情", hours, "签到时间", "签退时间", f"2025年12月{day}日", f"2025年12月{day}日",
             "12:33:03", end, "参与活动", "志愿服务活动"]
    boxes = [[280,100,620,150],[330,400,590,500],[150,550,310,590],[620,550,780,590],
             [70,650,380,690],[540,650,860,690],[150,720,320,760],[620,720,800,760],
             [40,1060,180,1100],[280,1060,860,1100]]
    return {"rec_texts":texts, "rec_scores":[.99]*len(texts), "rec_boxes":boxes}


def honor():
    texts = ["荣誉时数详情", "11.5", "+", "基础信息", "志愿者姓名", "张三", "录入人姓名", "李四",
             "录入组织名", "志愿服务中心", "录入时间", "2026-09-1810:26:21", "录入类型", "担保书补录",
             "录入原因", "2025.12.21、2025.12.22"]
    boxes = [[280,100,620,150],[430,400,590,500],[350,400,400,500],[40,600,200,640],
             [40,700,250,740],[750,700,900,740],[40,800,250,840],[750,800,900,840],
             [40,900,250,940],[500,900,900,940],[40,1000,250,1040],[400,1000,950,1040],
             [40,1100,250,1140],[600,1100,950,1140],[40,1200,250,1240],[400,1200,950,1240]]
    return {"rec_texts":texts,"rec_scores":[.99]*len(texts),"rec_boxes":boxes}


class Provider:
    def __init__(self, data): self.data = data
    def predict(self, path): return self.data


def policy(client, users, **overrides):
    login(client, users["admin"])
    config = dict(credit_rate="0.1", honor_rate="0.1", max_score="1", honor_enabled=True,
                  start_date="2025-01-01", end_date="2025-12-31")
    config.update(overrides)
    result = client.put("/api/automation/volunteer/policies/2025", json=config)
    assert result.status_code == 200, result.data
    db.session.expire_all()
    login(client, users["student"])


def upload(client, color="white", kind="credit", claim=None):
    data = {"material_type":kind, "year":"2025", "files":(io.BytesIO(image_bytes(color)), "example.png")}
    if claim is not None: data["claimed_hours"] = json.dumps([claim])
    result = client.post("/api/automation/volunteer/batches", data=data)
    assert result.status_code == 202, result.data
    return result.json["id"]


def view(client, batch): return client.get(f"/api/automation/volunteer/batches/{batch}").json


def submit(client, batch):
    result = client.post(f"/api/automation/volunteer/batches/{batch}/submit", json={"version":view(client,batch)["version"]})
    assert result.status_code == 201, result.data
    return result.json


def approve(client, users, batch, hours, dates=None):
    login(client, users["admin"])
    report = view(client,batch)
    row = report["rows"][0]
    detail = {"id":row["id"],"decision":"approved","confirmed_hours":hours}
    if dates is not None:
        detail["activity_dates"] = dates
        detail["comment"] = "管理员根据补充材料确认日期"
    return client.post(f"/api/automation/volunteer/batches/{batch}/review",
                       json={"version":report["version"],"status":"approved","items":[detail]})


def test_flow_and_score(env):
    app, client, users = env
    policy(client,users)
    batch = upload(client,claim=5.05)
    assert run_one(app,Provider(credit()))
    report = view(client,batch)
    assert report["rows"][0]["displayed_hours"] == 5.05
    assert report["estimated_incremental_score"] == "0.5050"
    submitted = submit(client,batch)
    assert db.session.get(Application,submitted["application_id"]).final_score is None
    result = approve(client,users,batch,"5.05")
    assert result.status_code == 200, result.data
    assert db.session.get(Application,submitted["application_id"]).final_score == .505
    assert Student.query.first().comprehensive_performance_total == .505
    assert AutomationReview.query.count() == 1


def test_file_and_activity_duplicate(env):
    app, client, users = env
    policy(client,users)
    original = upload(client)
    run_one(app,Provider(credit()))
    exact = upload(client)
    assert view(client,exact)["rows"][0]["status"] == "duplicate"
    altered = upload(client,color="gray")
    run_one(app,Provider(credit(hours="+50")))
    assert view(client,altered)["rows"][0]["status"] == "duplicate"
    result = client.post(f"/api/automation/volunteer/batches/{altered}/submit", json={"version":view(client,altered)["version"]})
    assert result.status_code == 400
    assert AutomationItem.query.filter_by(batch_id=original).first().status == "ready"


def test_cap_across_batches_and_revocation(env):
    app, client, users = env
    policy(client,users)
    first = upload(client)
    run_one(app,Provider(credit()))
    submit(client,first)
    assert approve(client,users,first,"5.05").status_code == 200
    login(client,users["student"])
    second = upload(client,color="gray")
    run_one(app,Provider(credit(day="22")))
    assert view(client,second)["estimated_incremental_score"] == "0.4950"
    second_view = submit(client,second)
    assert approve(client,users,second,"5.05").status_code == 200
    assert Student.query.first().comprehensive_performance_total == 1
    first_view = view(client,first)
    result = client.post(f"/api/automation/volunteer/batches/{first}/review", json={"version":first_view["version"],"status":"rejected"})
    assert result.status_code == 200
    assert db.session.get(Application,second_view["application_id"]).final_score == .505
    assert Student.query.first().comprehensive_performance_total == .505


def test_honor_and_wrong_type(env):
    app, client, users = env
    policy(client,users)
    batch = upload(client,kind="honor")
    run_one(app,Provider(honor()))
    row = view(client,batch)["rows"][0]
    assert row["displayed_hours"] == 11.5
    assert row["recorded_at"] == "2026-09-18T10:26:21"
    assert row["activity_dates"] == ["2025-12-21","2025-12-22"]
    submit(client,batch)
    assert approve(client,users,batch,"11.5").status_code == 200
    login(client,users["student"])
    wrong = upload(client,color="gray",kind="credit")
    run_one(app,Provider(honor()))
    assert view(client,wrong)["rows"][0]["status"] == "wrong_type"
    assert not view(client,wrong)["rows"][0]["can_submit"]


def test_permissions_and_legacy_bypass(env):
    app, client, users = env
    assert client.get("/api/automation/volunteer/batches").status_code == 401
    policy(client,users)
    batch = upload(client)
    run_one(app,Provider(credit()))
    report = submit(client,batch)
    application_id = report["application_id"]
    assert client.put(f"/api/applications/{application_id}",json={"status":"approved","finalScore":100}).status_code == 409
    assert client.delete(f"/api/applications/{application_id}").status_code == 409
    assert client.post(f"/api/applications/{application_id}/review",json={"status":"approved","finalScore":100}).status_code == 403
    login(client,users["other"])
    assert client.get(f"/api/automation/volunteer/batches/{batch}").status_code == 403
    assert client.get(f"/api/automation/items/{report['rows'][0]['id']}/image").status_code == 403


def test_policy_required_frozen_and_outside_period(env):
    app, client, users = env
    login(client,users["student"])
    batch = upload(client)
    run_one(app,Provider(credit()))
    assert view(client,batch)["estimated_incremental_score"] is None
    assert client.post(f"/api/automation/volunteer/batches/{batch}/submit",json={"version":view(client,batch)["version"]}).status_code == 409
    policy(client,users)
    submit(client,batch)
    login(client,users["admin"])
    cfg = client.get("/api/automation/volunteer/policies/2025").json["policy"]
    assert client.put("/api/automation/volunteer/policies/2025",json=cfg).status_code == 409


def test_malformed_and_mixed_upload(env):
    app, client, users = env
    login(client,users["student"])
    assert client.post("/api/automation/volunteer/batches",data={"year":"2025","material_type":"unknown","files":(io.BytesIO(image_bytes()),"x.png")}).status_code == 400
    result = client.post("/api/automation/volunteer/batches",data={"year":"2025","material_type":"credit","files":(io.BytesIO(b'not an image'),"x.jpg")})
    assert result.status_code == 400
    assert AutomationBatch.query.count() == 0


def test_stale_review_and_invalid_number(env):
    app, client, users = env
    policy(client,users)
    batch = upload(client)
    run_one(app,Provider(credit()))
    report = submit(client,batch)
    login(client,users["admin"])
    assert client.post(f"/api/automation/volunteer/batches/{batch}/review",json={"version":0,"status":"approved"}).status_code == 409
    for hours in ["NaN", "Infinity", "-1", True]:
        result = approve(client,users,batch,hours)
        assert result.status_code == 400
        db.session.rollback()
    assert db.session.get(Application,report["application_id"]).status == "pending"


def test_worker_failure_retry_and_lease(env):
    app, client, users = env
    policy(client,users)
    batch = upload(client)
    class Broken:
        def predict(self,path): raise RuntimeError("model unavailable")
    run_one(app,Broken())
    assert view(client,batch)["rows"][0]["status"] == "failed"
    assert client.post(f"/api/automation/volunteer/batches/{batch}/retry").status_code == 202
    record = db.session.get(AutomationBatch,batch)
    record.status, record.lease_token, record.lease_until = "processing", "old", datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(seconds=1)
    db.session.commit()
    run_one(app,Provider(credit()))
    assert view(client,batch)["rows"][0]["status"] == "ready"


def test_honor_requires_real_activity_date(env):
    app,client,users = env
    policy(client,users)
    batch = upload(client,kind="honor")
    data = honor()
    data["rec_texts"][-1] = "文艺演出"
    run_one(app,Provider(data))
    assert view(client,batch)["rows"][0]["activity_dates"] == []
    submit(client,batch)
    assert approve(client,users,batch,"11.5").status_code == 400
    db.session.rollback()
    assert approve(client,users,batch,"11.5",["2025-12-21"]).status_code == 200


def test_honor_same_activity_different_record_time(env):
    app, client, users = env
    policy(client,users)
    first = upload(client,kind="honor")
    run_one(app,Provider(honor()))
    second = upload(client,color="gray",kind="honor")
    data = honor()
    data["rec_texts"][11] = "2026-09-1910:26:21"
    run_one(app,Provider(data))
    assert view(client,second)["rows"][0]["status"] == "duplicate"


def test_batch_partial_duplicate_and_wrong_type(env):
    app,client,users = env
    policy(client,users)
    response = client.post("/api/automation/volunteer/batches", data={"material_type":"credit","year":"2025",
        "files":[(io.BytesIO(image_bytes()),"a.png"),(io.BytesIO(image_bytes()),"repeat.png"),
                 (io.BytesIO(image_bytes("black")),"honor.png")]})
    assert response.status_code == 202
    batch = response.json["id"]
    class Mixed:
        def predict(self,path):
            with Image.open(path) as im:
                return credit() if im.getpixel((0,0)) == (255,255,255) else honor()
    run_one(app,Mixed())
    rows = view(client,batch)["rows"]
    assert [x["status"] for x in rows] == ["ready","duplicate","wrong_type"]
    report = submit(client,batch)
    assert sum(x["submitted"] for x in report["rows"]) == 1


def test_disabled_honor_policy_and_period(env):
    app,client,users = env
    policy(client,users,honor_enabled=False)
    batch = upload(client,kind="honor")
    run_one(app,Provider(honor()))
    assert not view(client,batch)["rows"][0]["can_submit"]
    other = upload(client,color="gray")
    data = credit()
    data["rec_texts"][4] = data["rec_texts"][5] = "2026年12月21日"
    run_one(app,Provider(data))
    assert not view(client,other)["rows"][0]["can_submit"]


def test_worker_fencing_token(env):
    app,client,users = env
    policy(client,users)
    batch = upload(client)
    class Stale:
        def predict(self,path):
            record = db.session.get(AutomationBatch,batch)
            record.lease_token = "new-worker"
            db.session.commit()
            return credit()
    run_one(app,Stale())
    assert AutomationItem.query.filter_by(batch_id=batch).one().report is None


def test_unique_fingerprint_constraint(env):
    from automation_models import AutomationFingerprint
    from sqlalchemy.exc import IntegrityError
    app,client,users = env
    policy(client,users)
    batch = upload(client)
    entry = AutomationItem.query.filter_by(batch_id=batch).one()
    with pytest.raises(IntegrityError):
        with db.session.begin_nested():
            db.session.add(AutomationFingerprint(student_id="S1",kind="file",value=entry.sha256,item_id=entry.id))
            db.session.flush()


def test_submission_version_and_overrides(env):
    app,client,users = env
    policy(client,users)
    batch = upload(client)
    run_one(app,Provider(credit()))
    assert client.post(f"/api/automation/volunteer/batches/{batch}/submit",json={"version":0}).status_code == 409
    report = submit(client,batch)
    login(client,users["admin"])
    result = client.post(f"/api/applications/{report['application_id']}/review",json={
        "version":report["version"],"status":"approved","finalScore":100,
        "items":[{"id":report["rows"][0]["id"],"decision":"approved","confirmed_hours":"5.05"}]})
    assert result.status_code == 200
    assert db.session.get(Application,report["application_id"]).final_score == .505


def test_migration_tables(env):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from automation_models import AutomationFingerprint, AutomationPolicy
    app,client,users = env
    tables = [db.metadata.tables[n] for n in ["automation_policy","automation_batch","automation_item",
                                              "automation_fingerprint","automation_review"]]
    db.metadata.drop_all(bind=db.engine,tables=tables)
    path = Path(__file__).parents[1]/"migrations"/"versions"/"20261012_auto_materials.py"
    spec = importlib.util.spec_from_file_location("automation_migration",path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with db.engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            module.downgrade()
            module.upgrade()
    policy(client,users)
    batch = upload(client)
    assert AutomationBatch.query.count() == 1


def test_reclassify_keeps_history_and_cannot_change_submitted(env):
    app,client,users = env
    policy(client,users)
    batch = upload(client,kind="credit")
    run_one(app,Provider(honor()))
    result = client.post(f"/api/automation/volunteer/batches/{batch}/reclassify",json={
        "version":view(client,batch)["version"],"material_type":"honor"})
    assert result.status_code == 202, result.data
    run_one(app,Provider(honor()))
    assert view(client,batch)["rows"][0]["status"] == "ready"
    submitted = submit(client,batch)
    assert client.post(f"/api/automation/volunteer/batches/{batch}/reclassify",json={
        "version":submitted["version"],"material_type":"credit"}).status_code == 409
    repeated = upload(client)
    assert view(client,repeated)["rows"][0]["status"] == "duplicate"


def test_approval_partial_failure_rolls_back(env):
    app,client,users = env
    policy(client,users)
    response = client.post("/api/automation/volunteer/batches",data={"year":"2025","material_type":"credit",
         "files":[(io.BytesIO(image_bytes()),"a.png"),(io.BytesIO(image_bytes("gray")),"b.png")]})
    batch = response.json["id"]
    class Sequential:
        count = 0
        def predict(self,path):
            self.count += 1
            return credit(day=str(20+self.count))
    run_one(app,Sequential())
    report = submit(client,batch)
    login(client,users["admin"])
    rows = [{"id":report["rows"][0]["id"],"decision":"approved","confirmed_hours":"5.05"},
            {"id":report["rows"][1]["id"],"decision":"approved","confirmed_hours":"NaN"}]
    result = client.post(f"/api/automation/volunteer/batches/{batch}/review",json={
        "version":report["version"],"status":"approved","items":rows})
    assert result.status_code == 400
    db.session.expire_all()
    assert all(x.confirmed_hours is None and x.status == "ready" for x in db.session.get(AutomationBatch,batch).items)
    assert db.session.get(Application,report["application_id"]).status == "pending"


def test_native_flask_entry(monkeypatch):
    monkeypatch.setenv("DATABASE_URL","sqlite://")
    from app import app
    assert app.test_client().get("/api/health").status_code == 200
    assert app.test_client().get("/api/automation/volunteer/batches").status_code == 401
