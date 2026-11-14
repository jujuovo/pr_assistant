import unittest
from copy import deepcopy
from unittest.mock import patch
from PIL import Image

from src.zigzag_preprocess import prepare_zigzag_image
from test_watermark_preprocess import fixture


class ZigZagPreprocessTests(unittest.TestCase):
    def test_unverified_watermarks_never_load_algorithm(self):
        for words, status in ((["测试水印"]*3,"mismatched"),(["蓝桥材"]*3,"uncertain"),([], "missing")):
            image,data=fixture(words)
            with patch("src.zigzag_preprocess.load_zigzag") as loader:
                output,mask,report=prepare_zigzag_image(image,data)
            self.assertIsNone(output)
            self.assertEqual(report["status"],status)
            self.assertTrue(report["requires_manual_review"])
            loader.assert_not_called()

    def test_upstream_failure_requires_review_without_modifying_input(self):
        image,data=fixture(["蓝桥杯"]*4)
        before=image.tobytes()
        ocr_before=deepcopy(data)
        with patch("src.zigzag_preprocess.load_zigzag",side_effect=FileNotFoundError("missing upstream file")):
            output,mask,report=prepare_zigzag_image(image,data)
        self.assertIsNone(output)
        self.assertEqual(report["watermark_status"],"matched")
        self.assertEqual(report["status"],"uncertain")
        self.assertEqual(report["reason"],"zigzag_processing_failed")
        self.assertEqual(image.tobytes(),before)
        self.assertEqual(data,ocr_before)
        self.assertIsNone(mask.getbbox())

    def test_real_upstream_output_has_change_mask_and_preserves_input(self):
        image,data=fixture(["蓝桥杯"]*4)
        before=image.tobytes()
        ocr_before=deepcopy(data)
        output,mask,report=prepare_zigzag_image(image,data)
        self.assertIsNotNone(output)
        self.assertEqual(output.size,image.size)
        self.assertEqual(output.mode,"RGB")
        self.assertEqual(report["method"],"zigzag")
        self.assertEqual(report["mask_type"],"changed_pixels_not_watermark_segmentation")
        self.assertEqual(image.tobytes(),before)
        self.assertEqual(data,ocr_before)
        self.assertGreater(report["changed_pixels"],0)
        self.assertEqual(report["source"]["license"],"AGPL-3.0")

    def test_completely_erased_dark_ink_blocks_processed_ocr(self):
        import numpy as np
        from PIL import ImageDraw
        from types import SimpleNamespace
        image,data=fixture(["蓝桥杯"]*4)
        ImageDraw.Draw(image).rectangle((10,200,30,220),fill="black")
        module=SimpleNamespace(process=lambda rgb,**kwargs:(np.full_like(rgb,255),{}))
        with patch("src.zigzag_preprocess.load_zigzag",return_value=module):
            output,mask,report=prepare_zigzag_image(image,data)
        self.assertIsNone(output)
        self.assertEqual(report["reason"],"zigzag_erased_all_dark_ink")
        self.assertTrue(report["requires_manual_review"])


if __name__=="__main__":
    unittest.main()
