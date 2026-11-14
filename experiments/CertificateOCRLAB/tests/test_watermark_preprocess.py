import unittest
from copy import deepcopy
from math import cos,sin,radians

import numpy as np
from PIL import Image,ImageDraw

from src.watermark_preprocess import inspect_watermark,prepare_watermark_image


def polygon(x, y, angle=-30, width=80, height=18):
    a = radians(angle)
    c, s = cos(a), sin(a)
    return [[x + u*c - v*s, y + u*s + v*c]
            for u, v in [(0, 0), (width, 0), (width, height), (0, height)]]


def fixture(words):
    image=Image.new("RGB",(400,250),"white")
    polys=[polygon(50+i*100,70+i*25) for i in range(len(words))]
    draw=ImageDraw.Draw(image)
    for poly in polys:
        draw.polygon([tuple(p) for p in poly],fill=(225,225,225))
    return image,{"rec_texts":words,"rec_scores":[0.99]*len(words),"rec_polys":polys}


class WatermarkPreprocessTests(unittest.TestCase):
    def test_missing_blocks_cleaning_and_ocr(self):
        image=Image.new("RGB",(400,250),"white")
        data={"rec_texts":["蓝桥杯大赛"],"rec_scores":[0.99],"rec_polys":[polygon(40,80,0)]}
        output,mask,report=prepare_watermark_image(image,data)
        self.assertIsNone(output)
        self.assertEqual(report["status"],"missing")
        self.assertTrue(report["requires_manual_review"])
        self.assertEqual(np.count_nonzero(np.asarray(mask)),0)

    def test_different_repeated_word_is_mismatched(self):
        image,data=fixture(["测试水印"]*3)
        output,_,report=prepare_watermark_image(image,data)
        self.assertIsNone(output)
        self.assertEqual(report["status"],"mismatched")

    def test_fuzzy_only_needs_review(self):
        image,data=fixture(["蓝桥材"]*3)
        output,_,report=prepare_watermark_image(image,data)
        self.assertIsNone(output)
        self.assertEqual(report["status"],"uncertain")

    def test_single_match_needs_review(self):
        image,data=fixture(["蓝桥杯"])
        self.assertEqual(inspect_watermark(image,data)["status"],"uncertain")

    def test_valid_mask_preserves_original_dark_and_red_pixels(self):
        image,data=fixture(["蓝桥杯"]*4)
        draw=ImageDraw.Draw(image)
        draw.rectangle((70,64,76,73),fill=(20,20,20))
        draw.rectangle((81,64,87,73),fill=(210,20,20))
        before=np.asarray(image).copy()
        original_data=deepcopy(data)
        output,mask,report=prepare_watermark_image(image,data)
        self.assertEqual(report["status"],"matched")
        self.assertGreater(np.count_nonzero(np.asarray(mask)),0)
        self.assertEqual(report["dark_or_colored_pixels_changed"],0)
        np.testing.assert_array_equal(np.asarray(image),before)
        np.testing.assert_array_equal(np.asarray(output)[68,73],before[68,73])
        np.testing.assert_array_equal(np.asarray(output)[68,84],before[68,84])
        self.assertEqual(data,original_data)

    def test_missing_coordinates_needs_review(self):
        image=Image.new("RGB",(400,250),"white")
        report=inspect_watermark(image,{"rec_texts":["蓝桥杯"],"rec_scores":[0.99]})
        self.assertEqual(report["status"],"uncertain")


if __name__=="__main__":
    unittest.main()
