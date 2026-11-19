import importlib.util
import io
from datetime import timedelta
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from PIL import Image
from sqlalchemy import inspect

from automation_models import utcnow
from conftest import login
from extensions import db
from models import Application, User
from ocr_models import OCRJob
from services.competition_ocr.jobs import job_root
from services.competition_ocr.worker import run_one_ocr


class Provider:
    def __init__(self):
        self.calls = 0

    def predict(self, path):
        self.calls += 1
        texts = ["CSP认证成绩", "编号：CCF-IDEN-CSP-2025-98765", "姓名/NAME", "张三",
                 "日期", "/DATE", "2025.09.21", "TOTAL SCORES", "100", "100", "40", "0", "20", "260"]
        return {"rec_texts": texts, "rec_scores": [.99] * len(texts),
                "rec_polys": [[[10, i*20], [80, i*20], [80, i*20+12], [10, i*20+12]] for i in range(len(texts))]}


def upload(env):
    login(env[1], env[2]["student"])
    image = io.BytesIO()
    Image.new("RGB", (600, 600), "white").save(image, format="PNG")
    response = env[1].post("/api/ocr/csp/recognize", data={"file": (io.BytesIO(image.getvalue()), "sample.png")})
    assert response.status_code == 202, response.json
    return response.json["id"], image.getvalue()


def test_authenticated_ocr_queue_results_images_and_access(env):
    app, client, users = env
    assert client.get("/api/ocr/categories").status_code == 401
    job_id, original = upload(env)
    assert len(client.get("/api/ocr/categories").json["categories"]) == 7
    provider = Provider()
    assert provider.calls == 0 and OCRJob.query.count() == 1
    assert run_one_ocr(app, provider)
    result = client.get(f"/api/ocr/jobs/{job_id}").json
    assert result["report"]["fields"]["total_score"] == 260
    assert result["report"]["ocr_passes"] == 1 and provider.calls == 1
    assert result["artifact_urls"].keys() == {"original", "raw_ocr"}
    assert client.get(result["artifact_urls"]["original"]).data == original
    assert client.get(result["artifact_urls"]["raw_ocr"]).mimetype == "image/png"
    assert client.get(f"/api/ocr/jobs/{job_id}/images/unknown").status_code == 404
    from services.competition_ocr.jobs import job_root
    preserved = job_root(job_id) / result["report"]["images"]["original"]
    preserved.write_bytes(b"modified after processing")
    assert client.get(result["artifact_urls"]["original"]).status_code == 409
    preserved.write_bytes(original)
    assert Application.query.count() == 0  # OCR does not create or score an application.
    other_student = User(username="peer", password="x", name="同院学生", role="student", status="active",
                         faculty_id=db.session.get(User, users["student"]).faculty_id)
    db.session.add(other_student)
    db.session.commit()
    login(client, other_student.id)
    assert client.get(f"/api/ocr/jobs/{job_id}").status_code == 403
    login(client, users["other"])
    assert client.get(result["artifact_urls"]["original"]).status_code == 403
    login(client, users["admin"])
    assert client.get(f"/api/ocr/jobs/{job_id}").status_code == 200


def test_invalid_files_create_no_tasks(env):
    login(env[1], env[2]["student"])
    assert env[1].post("/api/ocr/csp/recognize", data=b"broken", content_type="image/png").status_code == 400
    assert env[1].post("/api/ocr/csp/recognize", json={}).status_code == 415
    assert env[1].post("/api/ocr/unknown/recognize", data=b"x", content_type="image/png").status_code == 404
    assert OCRJob.query.count() == 0


@pytest.mark.parametrize("failure", ["tampered", "expired"])
def test_original_tampering_and_retry_limit_prevent_model_calls(env, failure):
    job_id, _ = upload(env)
    row = db.session.get(OCRJob, job_id)
    if failure == "tampered":
        (job_root(job_id) / "input.png").write_bytes(b"changed")
    else:
        row.status, row.attempts, row.lease_token = "processing", 3, "old"
        row.lease_until = utcnow() - timedelta(seconds=1)
        db.session.commit()
    provider = Provider()
    assert run_one_ocr(env[0], provider)
    db.session.refresh(row)
    assert row.status == "failed" and row.report is None and provider.calls == 0


def test_old_worker_cannot_publish_after_losing_lease(env):
    job_id, _ = upload(env)
    class Stale(Provider):
        def predict(self, path):
            OCRJob.query.filter_by(id=job_id).update({"lease_token": "replacement"}, synchronize_session=False)
            db.session.commit()
            return super().predict(path)
    assert run_one_ocr(env[0], Stale())
    row = db.session.get(OCRJob, job_id)
    db.session.refresh(row)
    assert row.lease_token == "replacement" and row.status == "processing" and row.report is None


def test_new_migration_upgrade_downgrade(env):
    path = Path(__file__).parents[1] / "migrations/versions/20261118_ocr_jobs.py"
    spec = importlib.util.spec_from_file_location("ocr_migration_test", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    db.session.remove()
    OCRJob.__table__.drop(db.engine)
    with db.engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert {column["name"] for column in inspect(connection).get_columns("ocr_job")} == set(OCRJob.__table__.columns.keys())
            migration.downgrade()
            assert "ocr_job" not in inspect(connection).get_table_names()
            migration.upgrade()


@pytest.mark.skipif(__import__("os").environ.get("RUN_REAL_OCR") != "1", reason="需要本地真实OCR")
def test_real_merged_worker_uses_only_backend_samples_and_models(env):
    import os
    from services.recognition.provider import PaddleProvider
    provider = PaddleProvider(os.environ.get("OCR_MODEL_ROOT"))
    samples = Path(__file__).parents[1] / "samples"
    login(env[1], env[2]["student"])
    for key, path in (("csp", next((samples / "CSP").glob("*.jpg"))),
                      ("lanqiao", samples / "LanqiaoCup/example4.jpg")):
        response = env[1].post(f"/api/ocr/{key}/recognize",
            data={"file": (io.BytesIO(path.read_bytes()), path.name)})
        assert response.status_code == 202, response.json
        assert run_one_ocr(env[0], provider)
        report = env[1].get(response.json["result_url"]).json
        assert report["status"] in ("extracted", "manual_review"), report
        if key == "csp":
            assert report["report"]["fields"]["total_score"] == 260
        else:
            assert report["report"]["ocr_passes"] == 2
            assert report["report"]["fields"]["award"] == "二等奖"
        for url in report["artifact_urls"].values():
            assert env[1].get(url).status_code == 200
        data = dict(report["mapping"]["data"])
        if key == "csp":
            data["full_score"] = 500
        else:
            data.update(organizer="学生补充的主办单位", competition_level="省级")
        confirmed = env[1].post(f"/api/ocr/jobs/{response.json['id']}/confirm-material",
                                json={"year": 2026, "data": data})
        assert confirmed.status_code == 201, confirmed.json
        assert confirmed.json["material"]["ocr_links"][0]["suggestions"] == report["mapping"]
