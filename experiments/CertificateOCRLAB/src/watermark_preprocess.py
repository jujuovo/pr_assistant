"""Validate an expected textual watermark before modifying certificate pixels."""
from collections import Counter
from difflib import SequenceMatcher
from math import isfinite

import cv2
import numpy as np
from PIL import Image

from src.watermark_filter import (
    angle_distance, body_angle_for, box_angle, filter_watermarks, normalize_text, pale_foreground, valid_polygon,
)


def inspect_watermark(image, data, expected="蓝桥杯"):
    expected = normalize_text(expected)
    if not expected:
        raise ValueError("expected watermark must not be empty")
    report = {
        "expected_text": expected, "status": "uncertain",
        "requires_manual_review": True, "next_step": "manual_review",
        "candidates": [], "exact_match_count": 0,
    }
    if not isinstance(data,dict):
        report["reason"] = "invalid_ocr_data"
        return report
    texts, polys = data.get("rec_texts", []), data.get("rec_polys", [])
    if not isinstance(texts,(list,tuple)) or not isinstance(polys,(list,tuple,np.ndarray)):
        report["reason"] = "invalid_ocr_structure"
        return report
    try:
        polygon_count = len(polys)
    except TypeError:
        report["reason"] = "invalid_ocr_structure"
        return report
    if len(texts) != polygon_count:
        report["reason"] = "missing_or_inconsistent_ocr_geometry"
        return report
    scores = data.get("rec_scores", [])
    try:
        score_count = len(scores)
    except TypeError:
        report["reason"] = "invalid_ocr_scores"
        return report
    if not isinstance(scores,(list,tuple,np.ndarray)) or score_count != len(texts):
        report["reason"] = "missing_or_inconsistent_ocr_scores"
        return report
    if not all(isinstance(t,str) for t in texts):
        report["reason"] = "invalid_ocr_texts"
        return report
    if not all(valid_polygon(poly) for poly in polys):
        report["reason"] = "invalid_ocr_geometry"
        return report
    try:
        scores = [float(score) for score in scores]
        if not all(isfinite(score) and 0 <= score <= 1 for score in scores):
            raise ValueError("nonfinite or out of range OCR scores")
    except (TypeError,ValueError,OverflowError):
        report["reason"] = "invalid_ocr_scores"
        return report
    words = [normalize_text(text) for text in texts]
    angles = [box_angle(poly) for poly in polys]
    body_angle = body_angle_for(words, angles)
    report["body_angle"] = body_angle
    for i, (text, poly, score, word, angle) in enumerate(zip(texts, polys, scores, words, angles)):
        if not word or len(word) > 8 or angle is None:
            continue
        if not 12 <= angle_distance(angle, body_angle) <= 65:
            continue
        appearance = pale_foreground(image, poly)
        if not appearance or not appearance["is_pale"]:
            continue
        report["candidates"].append({
            "index": i, "text": text, "normalized_text": word, "score": float(score),
            "polygon": poly, "angle": angle, "appearance": appearance,
            "exact_match": word == expected and float(score) >= 0.8,
            "similarity": SequenceMatcher(None, word, expected).ratio(),
        })
    candidates = report["candidates"]
    exact = sum(c["exact_match"] for c in candidates)
    report["exact_match_count"] = exact
    if not candidates:
        report.update(status="missing", reason="no_pale_angled_watermark_detected")
    elif exact >= 2 and len(candidates) >= 3:
        report.update(
            status="matched", requires_manual_review=False,
            next_step="remove_watermark_then_ocr",
            reason="at_least_two_exact_matches_in_repeated_pale_watermarks",
        )
    elif any(c["similarity"] >= 0.6 for c in candidates):
        report.update(status="uncertain", reason="only_fuzzy_or_insufficient_exact_matches")
    else:
        counts = Counter(c["normalized_text"] for c in candidates if len(c["normalized_text"]) >= 2)
        if any(count >= 3 for count in counts.values()):
            report.update(status="mismatched", reason="repeated_watermark_text_does_not_match_expected")
        else:
            report.update(status="uncertain", reason="insufficient_evidence_for_watermark_identity")
    return report


def prepare_watermark_image(image, data, expected="蓝桥杯", gray_min=180, gray_max=245):
    """Whiten only eligible pale pixels inside verified watermark polygons."""
    if not 0 <= gray_min < gray_max <= 255:
        raise ValueError("gray thresholds must satisfy 0 <= min < max <= 255")
    original = image.convert("RGB")
    report = inspect_watermark(original, data, expected)
    height, width = original.height, original.width
    empty = np.zeros((height,width), dtype=np.uint8)
    if report["status"] != "matched":
        return None, Image.fromarray(empty), report
    filtered = filter_watermarks(data, watermark_texts=[expected], image_path=None)
    polygons = [
        block["polygon"] for block in filtered["watermark_filter"]["removed_blocks"]
        if block["reason"] != "empty_ocr_result" and block["polygon"]
    ]
    # Add pale fragments discovered with image evidence.
    # Candidate polygons are validated against original image brightness.
    polygons += [c["polygon"] for c in report["candidates"]]
    roi = np.zeros((height,width), dtype=np.uint8)
    for poly in polygons:
        cv2.fillPoly(roi, [np.round(np.asarray(poly)).astype(np.int32)], 255)
    radius = max(1, round(width / 1000))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius*2+1,radius*2+1))
    roi = cv2.dilate(roi,kernel)
    rgb = np.asarray(original)
    gray = cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    # Dark glyphs and saturated stamp/title colors are never whitened.
    protected = ((gray < gray_min) | (hsv[:,:,1] >= 70)).astype(np.uint8)*255
    protected = cv2.dilate(protected,kernel)
    eligible = (roi > 0) & (gray >= gray_min) & (gray < gray_max) & (protected == 0)
    mask = eligible.astype(np.uint8)*255
    changed = int(np.count_nonzero(mask))
    report.update(
        method="verified_watermark_polygon_and_pale_pixel_mask",
        gray_min=gray_min, gray_max=gray_max, saturation_protection=70,
        protection_radius=radius, roi_pixels=int(np.count_nonzero(roi)),
        changed_pixels=changed, changed_fraction=changed/(width*height),
        dark_or_colored_pixels_changed=int(np.count_nonzero(eligible & (protected > 0))),
    )
    if not changed or report["changed_fraction"] > 0.15:
        report.update(
            status="uncertain", requires_manual_review=True, next_step="manual_review",
            reason="empty_or_excessive_removal_mask",
        )
        return None, Image.fromarray(empty), report
    output = rgb.copy()
    output[eligible] = 255
    return Image.fromarray(output), Image.fromarray(mask), report
