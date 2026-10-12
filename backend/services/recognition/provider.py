"""模型实例仅由工作进程持有，HTTP 服务不导入 Paddle。"""
class PaddleProvider:
    def __init__(self):
        from paddleocr import PaddleOCR
        self.ocr = PaddleOCR(device="cpu", enable_mkldnn=False, cpu_threads=2,
                             text_detection_model_name="PP-OCRv5_mobile_det",
                             text_recognition_model_name="PP-OCRv5_mobile_rec",
                             use_doc_orientation_classify=False, use_doc_unwarping=False,
                             use_textline_orientation=False)

    def predict(self, path):
        results = list(self.ocr.predict(input=str(path)))
        if len(results) != 1:
            raise ValueError("仅支持单页图片")
        return results[0].json["res"]
