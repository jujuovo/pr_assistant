"""Validate an expected textual watermark before modifying certificate pixels."""
from collections import Counter
from difflib import SequenceMatcher
from statistics import median
from math import isfinite

import cv2
import numpy as np
from PIL import Image

from .watermark_filter import (
    angle_distance, box_angle, filter_watermarks, normalize_text, pale_foreground, valid_polygon,
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
    anchors = [
        box_angle(poly) for text,poly in zip(texts,polys)
        if len(normalize_text(text)) >= 6 and box_angle(poly) is not None
    ]
    body_angle = median(anchors) if anchors else 0.0
    report["body_angle"] = body_angle
    for i,(text,poly,score) in enumerate(zip(texts,polys,scores)):
        word, angle = normalize_text(text), box_angle(poly)
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

