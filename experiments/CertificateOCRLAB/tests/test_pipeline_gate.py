import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from PIL import Image
import main as entry
from test_core_reliability import args_for
from test_watermark_preprocess import fixture,polygon


class PipelineGateTests(TestCase):
    def run_pipeline(self,image,data,processed=None,method="zigzag"):
        with TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/"sample.png"
            image.save(source)
            output=root/"out"
            args = args_for(source, output)
            args.watermark_method = method
            responses=[([data],0.001)]
            if processed is not None:
                responses.append(([processed],0.001))
            with patch.object(entry,"parse_args",return_value=args), \
                 patch.object(entry,"run_ocr",side_effect=responses) as runner, \
                 patch.dict("sys.modules",{"paddleocr":SimpleNamespace(PaddleOCR=lambda **kwargs:object())}):
                entry.main()
            row=json.loads((output/"summary.json").read_text(encoding="utf-8"))["results"][0]
            if row.get("automatic_ocr_after_removal"):
                mask_name = "pixel_change_mask.png" if method == "zigzag" else "watermark_mask.png"
                self.assertTrue((output/"sample"/mask_name).is_file())
                self.assertEqual(row["certificate_authenticity"],"not_assessed")
            return row,runner.call_count,(output/"sample"/"processed.png").exists()

    def test_missing_watermark_does_not_run_second_ocr(self):
        image=Image.new("RGB",(400,250),"white")
        data={"rec_texts":["蓝桥杯大赛"],"rec_scores":[0.99],"rec_polys":[polygon(40,80,0)]}
        row,calls,has_processed=self.run_pipeline(image,data)
        self.assertEqual(calls,1)
        self.assertFalse(has_processed)
        self.assertFalse(row["automatic_ocr_after_removal"])
        self.assertEqual(row["watermark_check"]["status"],"missing")

    def test_matched_runs_second_ocr_and_flags_lost_award(self):
        image,data=fixture(["蓝桥杯"]*4)
        data["rec_texts"].append("福建赛区二等奖")
        data["rec_scores"].append(0.99)
        data["rec_polys"].append(polygon(40,200,0))
        processed={"rec_texts":["福建赛区等奖"],"rec_scores":[0.99],"rec_polys":[polygon(40,200,0)]}
        row,calls,has_processed=self.run_pipeline(image,data,processed)
        self.assertEqual(calls,2)
        self.assertTrue(has_processed)
        self.assertTrue(row["requires_manual_review"])
        self.assertEqual(row["ocr_comparison"]["differences"][0]["field"],"award")


    def test_mismatched_watermark_does_not_run_second_ocr(self):
        image,data=fixture(["测试水印"]*3)
        row,calls,has_processed=self.run_pipeline(image,data)
        self.assertEqual(calls,1)
        self.assertFalse(has_processed)
        self.assertEqual(row["watermark_check"]["status"],"mismatched")

    def test_upstream_failure_does_not_run_second_ocr(self):
        image,data=fixture(["蓝桥杯"]*4)
        with patch("src.zigzag_preprocess.load_zigzag",side_effect=RuntimeError("test failure")):
            row,calls,has_processed=self.run_pipeline(image,data)
        self.assertEqual(calls,1)
        self.assertFalse(has_processed)
        self.assertEqual(row["watermark_check"]["reason"],"zigzag_processing_failed")

    def test_legacy_mask_remains_selectable(self):
        image,data=fixture(["蓝桥杯"]*4)
        processed={"rec_texts":["福建赛区二等奖"],"rec_scores":[0.99],"rec_polys":[polygon(40,200,0)]}
        row,calls,has_processed=self.run_pipeline(image,data,processed,method="mask")
        self.assertEqual(calls,2)
        self.assertTrue(has_processed)
        self.assertEqual(row["watermark_check"]["mask_type"],"eligible_pale_watermark_pixels")
