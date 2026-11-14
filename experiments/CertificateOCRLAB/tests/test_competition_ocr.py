import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image

from src.competition_ocr.catalog import CATEGORIES, SAMPLES
from src.competition_ocr.http_api import create_server
from src.competition_ocr.service import CompetitionOCR, MAX_BYTES


def image_bytes(size=(150, 150)):
    with io.BytesIO() as output:
        Image.new("RGB", size, "white").save(output, format="PNG")
        return output.getvalue()


class Engine:
    def __init__(self, lines=(), polygons=()):
        self.lines = list(lines)
        self.polygons = polygons
        self.calls = 0

    def predict(self, image_path):
        self.calls += 1
        return {"rec_texts": self.lines, "rec_scores": [.96] * len(self.lines), "rec_polys": self.polygons}


class MaterialsTest(unittest.TestCase):
    def test_bad_image_does_not_invoke_model(self):
        engine = Engine()
        for data in (b"not an image", image_bytes((50, 150))):
            with self.assertRaises(ValueError):
                CompetitionOCR(engine).recognize_bytes(data, "csp")
        self.assertEqual(engine.calls, 0)

    def test_certificate_uses_specific_fields_and_leaves_ambiguous_award_empty(self):
        engine = Engine(["中国大学生计算机设计大赛", "作品《测试作品》", "参赛学生：张三、李四",
                         "等奖", "证书编号：2026001234设计", "指导教师：王五"])
        result = CompetitionOCR(engine).recognize_bytes(image_bytes(), "computer-design")
        self.assertEqual(result["fields"]["participants"], ["张三", "李四"])
        self.assertEqual(result["fields"]["certificate_no"], "2026001234")
        self.assertIsNone(result["fields"]["award"])
        self.assertEqual(result["status"], "manual_review")
        self.assertEqual(engine.calls, 1)

    def test_wrong_event_does_not_extract_award(self):
        result = CompetitionOCR(Engine(["中国大学生计算机设计大赛", "一等奖"])).recognize_bytes(
            image_bytes(), "challenge-cup")
        self.assertEqual(result["missing_fields"], ["event"])
        self.assertNotIn("award", result["fields"])

    def test_csp_uses_score_table_instead_of_ranking_numbers(self):
        engine = Engine(["CSP认证成绩", "编号：CCF-IDEN-CSP-2025-98765", "姓名/NAME", "张三",
                         "日期", "/DATE", "2025.09.21", "TOTAL SCORES",
                         "0", "100", "40", "0", "20", "160", "排名分析", "500"])
        result = CompetitionOCR(engine).recognize_bytes(image_bytes(), "csp")
        self.assertEqual(result["fields"]["total_score"], 160)
        self.assertEqual(result["fields"]["test_date"], "2025-09-21")
        self.assertNotIn("award", result["fields"])

    def test_social_practice_team_list_does_not_prove_personal_eligibility(self):
        result = CompetitionOCR(Engine(["优秀团队名单", "“实践一队”实践队"])).recognize_bytes(
            image_bytes(), "social-practice")
        self.assertEqual(result["fields"]["teams"], ["实践一队"])
        self.assertEqual(result["status"], "manual_review")
        self.assertEqual(result["authenticity"], "not_assessed")

    def test_image_export_is_opt_in_and_preserves_original_bytes(self):
        polygon = [[20, 30], [90, 30], [90, 60], [20, 60]]
        engine = Engine(["管理层任职证明"], [polygon])
        service = CompetitionOCR(engine)
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "sample.png"
            payload = image_bytes()
            source.write_bytes(payload)
            evidence = root / "result"
            result = service.recognize(source, "other", image_dir=evidence)
            self.assertEqual((evidence / result["images"]["original"]).read_bytes(), payload)
            with Image.open(evidence / result["images"]["raw_ocr"]) as overlay:
                self.assertNotEqual(overlay.getpixel((20, 30)), (255, 255, 255))
            self.assertNotIn("images", service.recognize_bytes(payload, "other"))
            with self.assertRaises(FileExistsError):
                service.recognize(source, "other", image_dir=evidence)

    def test_imported_sample_integrity(self):
        manifest = SAMPLES / "index.json"
        if not manifest.is_file():
            self.skipTest("未提供本地原图清单")
        rows = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual({row["category"] for row in rows}, set(CATEGORIES))
        self.assertEqual(len(rows), len({row["file"] for row in rows}))
        for row in rows:
            data = (SAMPLES / row["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), row["sha256"])


class HttpTest(unittest.TestCase):
    def test_http_accepts_image_bytes_and_rejects_invalid_uploads(self):
        engine = Engine(["管理层任职证明", "张三同学：", "于2025年9月至2026年7月担任测试社团社长。"])
        with create_server(CompetitionOCR(engine), 0) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}/api/ocr"
            try:
                with urlopen(base + "/categories", timeout=5) as response:
                    self.assertEqual(len(json.load(response)["categories"]), len(CATEGORIES))
                endpoint = base + "/other/recognize"
                with urlopen(Request(endpoint, image_bytes(), {"Content-Type": "image/png"}), timeout=5) as response:
                    self.assertEqual(json.load(response)["fields"]["position"], "社长")
                for payload, headers, status in [
                    (b"fake", {"Content-Type": "image/png"}, 400),
                    (b"x", {"Content-Type": "text/plain"}, 415),
                    (b"x", {"Content-Type": "image/png", "Content-Length": str(MAX_BYTES + 1)}, 413),
                ]:
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(Request(endpoint, payload, headers), timeout=5)
                    self.assertEqual(caught.exception.code, status)
                    caught.exception.close()
            finally:
                server.shutdown()
                thread.join()
        self.assertEqual(engine.calls, 1)
