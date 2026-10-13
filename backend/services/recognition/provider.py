"""主项目自己的模型；模型实例仅由工作进程持有。"""
from pathlib import Path


class PaddleProvider:
    def __init__(self, model_root=None):
        from paddleocr import PaddleOCR
        root = Path(model_root) if model_root else Path(__file__).resolve().parents[2] / "ocr-models"
        models = {"text_detection_model_dir": root / "PP-OCRv5_mobile_det",
                  "text_recognition_model_dir": root / "PP-OCRv5_mobile_rec"}
        local = {key: str(path) for key, path in models.items() if (path / "inference.yml").is_file()}
        if len(local) != 2:
            raise RuntimeError("本项目OCR模型未准备：请在backend运行 ../.venv/Scripts/python.exe tools/setup_certificate_models.py")
        self.ocr = PaddleOCR(device="cpu", enable_mkldnn=False, cpu_threads=4,
                             text_detection_model_name="PP-OCRv5_mobile_det",
                             text_recognition_model_name="PP-OCRv5_mobile_rec",
                             use_doc_orientation_classify=False, use_doc_unwarping=False,
                             use_textline_orientation=False, **local)

    def _predict(self, path, **options):
        results = list(self.ocr.predict(input=str(path), **options))
        if len(results) != 1:
            raise ValueError("仅支持单页图片")
        return results[0].json["res"]

    def predict(self, path):
        return self._predict(path)

    def predict_certificate(self, path):
        return self._predict(path, text_det_limit_type="max", text_det_limit_side_len=960, text_det_box_thresh=0.4)
