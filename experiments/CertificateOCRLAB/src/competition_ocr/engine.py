"""Lazy local PaddleOCR setup; share one model across a batch."""
from pathlib import Path

from src.ocr_runtime import create_paddle, prediction_options


class PaddleEngine:
    def __init__(self, model_root=None):
        self.root = Path(model_root or Path.home() / ".paddlex" / "official_models")
        self.model = None

    def predict(self, path):
        if self.model is None:
            self.model = create_paddle(model_root=self.root)
        pages = list(self.model.predict(str(path), **prediction_options()))
        if len(pages) != 1:
            raise ValueError("OCR 未返回一张图片对应的结果")
        return pages[0].json["res"]
