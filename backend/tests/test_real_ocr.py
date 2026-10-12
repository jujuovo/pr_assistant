"""可选真实 OCR 集成测试，样本放在本项目 tests/artifacts/samples。"""
import os
from pathlib import Path
import pytest
from conftest import login
from test_automation import policy, view
from services.recognition.provider import PaddleProvider
from services.recognition.worker import run_one


@pytest.mark.skipif(os.environ.get("RUN_REAL_OCR") != "1", reason="设置 RUN_REAL_OCR=1 启用真实模型验证")
def test_real_samples(env):
    app,client,users = env
    policy(client,users,end_date="2026-12-31")
    provider = PaddleProvider()
    results = []
    for name, kind, expected in [("example1.jpg","honor",12), ("example2.jpg","credit",5.05), ("example3.jpg","honor",11.5)]:
        path = Path(__file__).parent/"artifacts"/"samples"/name
        assert path.exists(), f"缺少本项目测试样本：{path}"
        with path.open("rb") as image:
            response = client.post("/api/automation/volunteer/batches",data={"material_type":kind,"year":"2025","files":(image,name)})
        assert response.status_code == 202
        run_one(app,provider)
        report = view(client,response.json["id"])
        assert report["rows"][0]["displayed_hours"] == expected
        assert report["rows"][0]["status"] == "ready"
        if kind == "credit":
            assert report["rows"][0]["check_in"] == "2025-12-21T12:33:03"
        results.append(report)
    import json
    output = Path(__file__).parent/"artifacts"/"real_preview.json"
    output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
