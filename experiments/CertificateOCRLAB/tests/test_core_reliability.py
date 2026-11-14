"""Regression checks for real failure paths discovered in the core-code review."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
import main as entry
from src.ocr_comparison import compare_ocr_fields
from src.watermark_preprocess import inspect_watermark
from test_watermark_preprocess import fixture


def args_for(source,output):
    return SimpleNamespace(
        input=source,output=output,model="mobile",cpu_threads=4,det_max_side=960,det_box_thresh=0.4,
        preprocess_watermark=True,expected_watermark="蓝桥杯",gray_min=180,gray_max=245,
        watermark_text=None,no_watermark_filter=False,watermark_method="zigzag",
        zigzag_size=30,zigzag_weight=90,zigzag_threshold_offset=0)


class CoreReliabilityTests(unittest.TestCase):
    def test_default_entry_targets_lanqiao_samples_and_mobile_zigzag(self):
        with patch("sys.argv",["main.py"]):
            args=entry.parse_args()
        self.assertEqual(args.input, entry.IMAGE_PATH)
        self.assertEqual(args.input.name, "LanqiaoCup")
        self.assertEqual(args.model,"mobile")
        self.assertTrue(args.preprocess_watermark)
        self.assertEqual(args.watermark_method,"zigzag")

    def test_existing_result_directory_is_never_overwritten(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/"sample.png";Image.new("RGB",(40,40),"white").save(source)
            out=root/"out";out.mkdir();marker=out/"processed.png";marker.write_bytes(b"previous evidence")
            with patch.object(entry,"parse_args",return_value=args_for(source,out)):
                with self.assertRaises(FileExistsError):
                    entry.main()
            self.assertEqual(marker.read_bytes(),b"previous evidence")

    def test_output_cannot_overlap_input(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);Image.new("RGB",(40,40),"white").save(root/"sample.png")
            with self.assertRaises(ValueError):
                entry.plan_inputs(args_for(root,root/"out"))

    def test_same_stem_images_have_separate_results(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/"in";source.mkdir()
            for name in ("sample.jpg","sample.png"):
                Image.new("RGB",(40,40),"white").save(source/name)
            plan=entry.plan_inputs(args_for(source,root/"out"))
            self.assertEqual(len({target.name.casefold() for _,target in plan}),2)

    def test_raw_ocr_failure_does_not_stop_other_images(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/"in";source.mkdir()
            for name in ("a.png","b.png"):
                Image.new("RGB",(40,40),"white").save(source/name)
            data={"rec_texts":[],"rec_polys":[],"rec_scores":[]}
            with patch.object(entry,"parse_args",return_value=args_for(source,root/"out")), \
                 patch.object(entry,"run_ocr",side_effect=[RuntimeError("failed image"),([data],0.001)]), \
                 patch.dict("sys.modules",{"paddleocr":SimpleNamespace(PaddleOCR=lambda **kw:object())}):
                code=entry.main()
            import json
            summary=json.loads((root/"out/summary.json").read_text(encoding="utf-8"))
            self.assertEqual(code,1)
            self.assertEqual(len(summary["results"]),2)
            self.assertEqual(summary["results"][0]["error_stage"],"raw_ocr")
            self.assertEqual(summary["results"][1]["watermark_check"]["status"],"missing")

    def test_second_ocr_failure_retains_original_fields_and_evidence(self):
        image,data=fixture(["蓝桥杯"]*4)
        data["rec_texts"].append("福建赛区二等奖")
        data["rec_scores"].append(0.99);data["rec_polys"].append([[10,180],[150,180],[150,200],[10,200]])
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/"sample.png";image.save(source)
            with patch.object(entry,"parse_args",return_value=args_for(source,root/"out")), \
                 patch.object(entry,"run_ocr",side_effect=[([data],0.001),RuntimeError("second OCR failed")]), \
                 patch.dict("sys.modules",{"paddleocr":SimpleNamespace(PaddleOCR=lambda **kw:object())}):
                entry.main()
            import json
            row=json.loads((root/"out/sample/result.json").read_text(encoding="utf-8"))
            self.assertEqual(row["error_stage"],"processed_ocr")
            self.assertTrue(row["processed_ocr_attempted"])
            self.assertFalse(row["automatic_ocr_after_removal"])
            self.assertEqual(row["raw_fields"]["award"],"二等奖")
            self.assertEqual((root/"out/sample/original.png").read_bytes(),source.read_bytes())

    def test_malformed_geometry_or_scores_returns_uncertain(self):
        for value in ([[1]], [[float("nan"),2],[3,4],[5,6],[7,8]],None):
            image,data=fixture(["蓝桥杯"]*3)
            data["rec_polys"][0]=value
            self.assertEqual(inspect_watermark(image,data)["status"],"uncertain")
        for value in (float("nan"),float("inf"),2.0,"invalid"):
            image,data=fixture(["蓝桥杯"]*3)
            data["rec_scores"][0]=value
            self.assertEqual(inspect_watermark(image,data)["status"],"uncertain")

    def test_both_ocr_passes_missing_fields_require_review(self):
        result=compare_ocr_fields([],[])
        self.assertTrue(result["requires_manual_review"])
        self.assertIn("award",result["missing_fields"])
        self.assertIn("certificate_no",result["missing_fields"])

    def test_invalid_dates_and_truncated_groups_require_review(self):
        result=compare_ocr_fields(["2026年99月99日","学A组"],["2026年99月99日","学A组"])
        self.assertIn("date",result["invalid_fields"])
        self.assertIn("group",result["invalid_fields"])


if __name__=="__main__":
    unittest.main()
