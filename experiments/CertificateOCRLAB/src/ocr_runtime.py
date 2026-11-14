"""Shared model options and OCR response validation."""
import os
from math import isfinite

DEFAULT_SIDE = 960
DEFAULT_BOX_THRESHOLD = .4


def create_paddle(model="mobile", cpu_threads=4, model_root=None):
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    detection, recognition = f"PP-OCRv5_{model}_det", f"PP-OCRv5_{model}_rec"
    paths = {}
    if model_root is not None:
        for key, name in (("text_detection_model_dir", detection), ("text_recognition_model_dir", recognition)):
            path = model_root / name
            if not (path / "inference.yml").is_file():
                raise RuntimeError(f"未找到本地 OCR 模型：{name}，请使用 --model-root 指定模型目录")
            paths[key] = str(path)
    from paddleocr import PaddleOCR
    return PaddleOCR(
        device="cpu", cpu_threads=cpu_threads, enable_mkldnn=False,
        text_detection_model_name=detection, text_recognition_model_name=recognition,
        use_doc_orientation_classify=False, use_doc_unwarping=False,
        use_textline_orientation=False, **paths,
    )


def prediction_options(side=DEFAULT_SIDE, threshold=DEFAULT_BOX_THRESHOLD):
    options = {}
    if side is not None:
        options.update(text_det_limit_type="max", text_det_limit_side_len=side)
    if threshold is not None:
        options["text_det_box_thresh"] = threshold
    return options


def validate_page(page):
    texts, scores = page.get("rec_texts"), page.get("rec_scores")
    if not isinstance(texts, list) or any(not isinstance(text, str) for text in texts):
        raise ValueError("OCR返回了无效文字结构")
    try:
        if len(scores) != len(texts) or not all(isfinite(float(s)) and 0 <= float(s) <= 1 for s in scores):
            raise ValueError("OCR分数缺失、无效或与文字数量不一致")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("OCR返回了无效识别分数") from exc
    return page
