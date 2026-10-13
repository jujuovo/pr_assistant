"""Verified-watermark gate plus the pinned upstream ZigZag CPU color algorithm."""
from functools import lru_cache
import hashlib
import importlib.util
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
from PIL import Image

from .watermark_preprocess import inspect_watermark

SOURCE = Path(__file__).resolve().parents[2] / "third_party/zigzag/zigzag.py"
SOURCE_COMMIT = "cec0d646034b6095f5a091b804144b58cc95d1cf"


@lru_cache(maxsize=1)
def load_zigzag():
    """Load only ZigZag; no untext, ML inpainting or optional detector imports."""
    spec = importlib.util.spec_from_file_location("certificate_zigzag_upstream", SOURCE)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load ZigZag source: {SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_zigzag_image(image, data, expected="蓝桥杯", size=30, weight=90, threshold_offset=0):
    """Return (OCR auxiliary image, pixel-change mask, audit report).

    The mask describes ALL modified pixels, not a segmentation of the watermark.
    The input image and OCR data remain unchanged. Non-matching watermarks and
    upstream failures never proceed to processed-image OCR.
    """
    if size <= 0:
        raise ValueError("zigzag size must be positive")
    if not 1 <= weight <= 100:
        raise ValueError("zigzag weight must be in [1, 100]")
    if not -255 <= threshold_offset <= 255:
        raise ValueError("zigzag threshold offset must be in [-255, 255]")
    original = image.convert("RGB")
    report = inspect_watermark(original, data, expected)
    report.update(
        method="zigzag",
        watermark_status=report["status"],
        mask_type="changed_pixels_not_watermark_segmentation",
        mask_filename="pixel_change_mask.png",
        parameters={"mode":"color", "size":size, "weight":weight,
                    "threshold_offset":threshold_offset, "backend":"cpu", "upsample":False},
        output_role="ocr_auxiliary_image",
        certificate_authenticity="not_assessed",
    )
    empty = Image.new("L", original.size)
    if report["status"] != "matched":
        return None, empty, report

    start = perf_counter()
    rgb = np.asarray(original)
    try:
        processed, info = load_zigzag().process(
            rgb, mode="color", size=size, weight=weight, upsample=False,
            backend="cpu", threshold_offset=threshold_offset,
        )
        if processed.shape != rgb.shape or processed.dtype != np.uint8:
            raise ValueError("ZigZag returned an invalid RGB shape or dtype")
        changed = np.any(processed != rgb, axis=2)
        original_gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        processed_gray = cv2.cvtColor(processed, cv2.COLOR_RGB2GRAY)
        original_hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        processed_hsv = cv2.cvtColor(processed, cv2.COLOR_RGB2HSV)
        dark = original_gray < 130
        red_original = (((original_hsv[:,:,0] < 10) | (original_hsv[:,:,0] > 170))
                        & (original_hsv[:,:,1] >= 100) & (original_hsv[:,:,2] > 50))
        red_processed = (((processed_hsv[:,:,0] < 10) | (processed_hsv[:,:,0] > 170))
                         & (processed_hsv[:,:,1] >= 100) & (processed_hsv[:,:,2] > 50))
        report.update(
            upstream_info=info,
            source={"path":str(SOURCE), "repository":"https://github.com/Bloechle/zigzag",
                    "commit":SOURCE_COMMIT, "sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                    "license":"AGPL-3.0"},
            changed_pixels=int(changed.sum()), changed_fraction=float(changed.mean()),
            dark_pixels_changed=int(np.count_nonzero(changed & dark)),
            colored_pixels_changed=int(np.count_nonzero(changed & (original_hsv[:,:,1]>=70))),
            dark_ink_whitened_fraction=float(np.count_nonzero(dark & (processed_gray>=220))/max(1,np.count_nonzero(dark))),
            red_color_retention=float(np.count_nonzero(red_original & red_processed)/max(1,np.count_nonzero(red_original))),
            processing_note="ZigZag normalizes the whole image and can alter borders, dark ink and colors. Use the original for evidence review; pixel metrics are not authenticity scores.",
            preprocess_seconds=round(perf_counter()-start,4),
        )
        if np.any(dark) and not np.any(processed_gray < 130):
            report.update(status="uncertain", reason="zigzag_erased_all_dark_ink",
                          requires_manual_review=True, next_step="manual_review")
            return None, Image.fromarray(changed.astype(np.uint8)*255), report
        return Image.fromarray(processed), Image.fromarray(changed.astype(np.uint8)*255), report
    except Exception as exc:
        report.update(status="uncertain", reason="zigzag_processing_failed", error=str(exc),
                      requires_manual_review=True, next_step="manual_review",
                      preprocess_seconds=round(perf_counter()-start,4))
        return None, empty, report
