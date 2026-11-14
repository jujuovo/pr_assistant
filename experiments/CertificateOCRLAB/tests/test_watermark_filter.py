import unittest
from copy import deepcopy
from src.watermark_filter import filter_watermarks
from PIL import Image, ImageDraw
from pathlib import Path
from tempfile import TemporaryDirectory

from test_watermark_preprocess import polygon


def result(texts, angles):
    return {
        "rec_texts": texts, "rec_scores": [0.99]*len(texts),
        "rec_polys": [polygon(100, i*40, angle, height=20) for i,angle in enumerate(angles)],
        "rec_boxes": [[100,i*40,180,i*40+20] for i in range(len(texts))],
    }


class WatermarkFilterTests(unittest.TestCase):
    def test_repeated_marks_removed_but_title_and_fields_preserved(self):
        data = result(["蓝桥杯", "蓝桥杯", "蓝桥杯", "蓝桥杯大赛",
                       "学生姓名：蓝桥杯", "1234567801", ""], [-35,-35,-35,0,0,0,0])
        before = deepcopy(data)
        out = filter_watermarks(data)
        self.assertEqual(out["rec_texts"], ["蓝桥杯大赛", "学生姓名：蓝桥杯", "1234567801"])
        self.assertEqual(data, before)
        self.assertEqual(out["watermark_filter"]["watermark_removed"], 3)
        self.assertEqual(out["watermark_filter"]["empty_removed"], 1)
        for key in ("rec_texts", "rec_scores", "rec_polys", "rec_boxes"):
            self.assertEqual(len(out[key]), 3)

    def test_isolated_diagonal_text_is_preserved(self):
        data = result(["蓝桥杯", "学校名称：厦门大学"], [-35,0])
        self.assertEqual(filter_watermarks(data, watermark_texts=["蓝桥杯"])["rec_texts"], data["rec_texts"])

    def test_document_tilt_is_relative_to_body(self):
        data = result(["学校名称：厦门大学", "荣获福建赛区一等奖",
                       "蓝桥杯", "蓝桥杯", "蓝桥杯", "1234567801"], [30,30,-5,-5,-5,30])
        out = filter_watermarks(data)
        self.assertEqual(out["watermark_filter"]["body_angle"], 30)
        self.assertEqual(out["rec_texts"], [data["rec_texts"][0],data["rec_texts"][1],"1234567801"])

    def test_pale_fragment_removed_but_dark_title_kept(self):
        data = result(["蓝桥杯", "蓝桥杯", "蓝桥杯", "蓝桥", "蓝桥", "学校名称：厦门大学"],
                      [-35,-35,-35,0,0,0])
        image = Image.new("RGB", (300, 300), "white")
        draw = ImageDraw.Draw(image)
        draw.polygon([tuple(p) for p in data["rec_polys"][3]], fill=(225,225,225))
        draw.polygon([tuple(p) for p in data["rec_polys"][4]], fill=(20,20,20))
        with TemporaryDirectory() as temp:
            path = Path(temp) / "sample.png"
            image.save(path)
            out = filter_watermarks(data, image_path=path)
        self.assertEqual(out["rec_texts"], ["蓝桥", "学校名称：厦门大学"])
        self.assertEqual(out["rec_polys"][0], data["rec_polys"][4])

    def test_missing_geometry_does_not_guess(self):
        data = {"rec_texts": ["蓝桥杯"]*3, "rec_scores": [0.99]*3}
        self.assertEqual(filter_watermarks(data)["rec_texts"], data["rec_texts"])


if __name__ == "__main__":
    unittest.main()
