import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image

import main as entry
import evaluate_zigzag as evaluator
from src.ocr_comparison import compare_ocr_fields, extract_fields
from src.watermark_preprocess import inspect_watermark
from test_core_reliability import args_for
from test_watermark_preprocess import fixture


class RecheckTests(unittest.TestCase):
    def test_output_reserved_before_model_initialization(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/"sample.png";Image.new("RGB",(40,40),"white").save(source)
            def factory(**kwargs):
                with self.assertRaises(FileExistsError):
                    entry.plan_inputs(args_for(source,root/"out"))
                return object()
            data={"rec_texts":[],"rec_scores":[],"rec_polys":[]}
            with patch.object(entry,"parse_args",return_value=args_for(source,root/"out")), \
                 patch.object(entry,"run_ocr",return_value=([data],0.001)), \
                 patch.dict("sys.modules",{"paddleocr":SimpleNamespace(PaddleOCR=factory)}):
                entry.main()

    def test_model_startup_failure_has_persisted_run_state(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/"sample.png";Image.new("RGB",(40,40),"white").save(source)
            with patch.object(entry,"parse_args",return_value=args_for(source,root/"out")), \
                 patch.dict("sys.modules",{"paddleocr":SimpleNamespace(PaddleOCR=lambda **kw:(_ for _ in ()).throw(RuntimeError("init failed")))}):
                with self.assertRaises(RuntimeError):
                    entry.main()
            marker=json.loads((root/"out/run.json").read_text(encoding="utf-8"))
            self.assertEqual(marker["status"],"startup_failed")

    def test_other_label_cannot_fill_a_missing_school(self):
        texts=["学校名称：","学生姓名：张三","指导老师：李四","第十七届","Python程序设计","大学A组",
               "福建赛区二等奖","证书编号：1234567802","2026年5月8日"]
        result=compare_ocr_fields(texts,texts)
        self.assertIsNone(result["processed_fields"]["school"])
        self.assertIn("school",result["missing_fields"])
        self.assertTrue(result["requires_manual_review"])

    def test_inline_next_label_is_not_part_of_school_name(self):
        fields=extract_fields(["学校名称：厦门大学学生姓名：张三","指导老师：李四"])
        self.assertEqual(fields["school"],"厦门大学")

    def test_zero_dimensional_ocr_arrays_require_review(self):
        image,data=fixture(["蓝桥杯"]*3)
        for key in ("rec_scores","rec_polys"):
            self.assertEqual(inspect_watermark(image,{**data,key:np.array(0.99)})["status"],"uncertain")

    def test_corrupt_summary_type_does_not_hide_a_valid_run(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);(root/"outputs").mkdir()
            for name,data in (("valid",{"image_preprocessing_enabled":True,"watermark_method":"zigzag"}),("invalid",[])):
                d=root/"outputs"/name;d.mkdir()
                (d/"summary.json").write_text(json.dumps(data),encoding="utf-8")
            with patch.object(evaluator,"ROOT",root):
                self.assertEqual(evaluator.latest_output().name,"valid")

    def test_evaluator_rejects_paths_outside_result_directory(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/"out";out.mkdir()
            summary={"image_preprocessing_enabled":True,"watermark_method":"zigzag","results":[
                {"file":"example4.jpg","output_subdir":"../outside","requires_manual_review":True,
                 "automatic_ocr_after_removal":False}]}
            (out/"summary.json").write_text(json.dumps(summary),encoding="utf-8")
            with self.assertRaises(ValueError):
                evaluator.evaluate(out)
