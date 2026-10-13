"""Conservative OCR watermark filtering; original image and OCR stay unchanged."""
from collections import Counter
from copy import deepcopy
from difflib import SequenceMatcher
from math import atan2, degrees, isfinite
from statistics import median
from numbers import Real
import re

from PIL import Image, ImageDraw


def normalize_text(text):
    return re.sub(r"[\s，。:：、._\-—]", "", str(text))


def valid_polygon(poly):
    try:
        return len(poly) >= 4 and all(len(point)==2 and all(isinstance(v,Real) and isfinite(float(v)) for v in point) for point in poly)
    except (TypeError,ValueError,OverflowError):
        return False


def box_angle(poly):
    if not valid_polygon(poly):
        return None
    dx = float(poly[1][0])-float(poly[0][0])
    dy = float(poly[1][1])-float(poly[0][1])
    if dx==0 and dy==0:
        return None
    return (degrees(atan2(dy,dx))+90)%180-90


def angle_distance(a, b):
    return abs((a - b + 90) % 180 - 90)


def pale_foreground(image, poly):
    """Use only pixels inside the polygon; ignore almost white background."""
    if image is None or not valid_polygon(poly):
        return None
    xs, ys = zip(*poly)
    left, top = max(0, int(min(xs))), max(0, int(min(ys)))
    right, bottom = min(image.width, int(max(xs)) + 1), min(image.height, int(max(ys)) + 1)
    if right <= left or bottom <= top:
        return None
    crop = image.crop((left, top, right, bottom)).convert("L")
    mask = Image.new("L", crop.size)
    ImageDraw.Draw(mask).polygon([(x-left, y-top) for x,y in poly], fill=255)
    histogram = crop.histogram(mask=mask)
    total = sum(histogram)
    foreground = sum(histogram[:245])
    if not foreground or not total:
        return None
    cumulative = 0
    foreground_median = 244
    for value, count in enumerate(histogram[:245]):
        cumulative += count
        if cumulative >= foreground / 2:
            foreground_median = value
            break
    return {
        "foreground_median": foreground_median,
        "dark_pixel_fraction": sum(histogram[:130]) / total,
        "is_pale": foreground_median >= 170 and sum(histogram[:130]) / total < 0.03,
    }


def filter_watermarks(data, image_path=None, watermark_texts=None):
    """Filter repeated short angled marks; never delete horizontal text by word alone.

    rec_texts, rec_scores, rec_polys, rec_boxes remain aligned. dt_polys is
    the original detector output and is deliberately retained for diagnosis.
    """
    texts = list(data.get("rec_texts", []))
    scores = list(data.get("rec_scores", []))
    polys = data.get("rec_polys", [])
    if len(scores) != len(texts):
        raise ValueError("rec_texts and rec_scores must have the same length")
    # Missing geometry prevents watermark decisions, rather than guessing.
    geometry = len(polys) == len(texts)
    angles = [box_angle(p) for p in polys] if geometry else [None] * len(texts)
    normalized = [normalize_text(t) for t in texts]
    anchors = [
        a for t, a in zip(normalized, angles)
        if a is not None and len(t) >= 6
    ]
    body_angle = median(anchors) if anchors else 0.0
    candidates = [
        i for i, (t, a) in enumerate(zip(normalized, angles))
        if 1 <= len(t) <= 4 and a is not None
        and 8 <= angle_distance(a, body_angle) <= 65
    ]
    references = [normalize_text(t) for t in (watermark_texts or []) if normalize_text(t)]
    if not references:
        counts = Counter(normalized[i] for i in candidates if len(normalized[i]) >= 2)
        references = [text for text, count in counts.items() if count >= 3]

    def similar(text):
        return any(
            text in ref or SequenceMatcher(None, text, ref).ratio() >= 0.6
            for ref in references
        )

    matches = [i for i in candidates if similar(normalized[i])]
    # An isolated tilted word is insufficient evidence for a watermark.
    repeated = len(matches) >= 3
    watermark_angle = median([angles[i] for i in matches]) if repeated else None
    image = None
    if image_path is not None:
        with Image.open(image_path) as source:
            image = source.convert("RGB")

    removed, keep = [], []
    for i, text in enumerate(texts):
        reason = None
        appearance = None
        if not normalized[i]:
            reason = "empty_ocr_result"
        elif repeated and i in candidates and similar(normalized[i]):
            reason = "repeated_short_angled_watermark"
        elif (
            repeated and image is not None and geometry
            and 1 <= len(normalized[i]) <= 4 and similar(normalized[i])
        ):
            # OCR sometimes gives a partial watermark a nearly horizontal box.
            # Pale pixels distinguish these fragments from the dark title.
            appearance = pale_foreground(image, polys[i])
            if appearance and appearance["is_pale"]:
                reason = "pale_fragment_of_repeated_watermark"
        elif (
            repeated and image is not None and i in candidates
            and angle_distance(angles[i], watermark_angle) <= 25
        ):
            appearance = pale_foreground(image, polys[i])
            if appearance and appearance["is_pale"]:
                reason = "pale_short_text_in_repeated_watermark_pattern"
        if reason:
            removed.append({
                "index": i, "text": text, "score": scores[i],
                "polygon": polys[i] if geometry else None,
                "angle": angles[i], "reason": reason, "appearance": appearance,
            })
        else:
            keep.append(i)

    filtered = deepcopy(data)
    for key in ("rec_texts", "rec_scores", "rec_polys", "rec_boxes", "textline_orientation_angles"):
        values = data.get(key)
        if isinstance(values, (list, tuple)) and len(values) == len(texts):
            filtered[key] = [deepcopy(values[i]) for i in keep]
    metadata = {
        "method": "repeated_short_text_angle_and_pale_foreground",
        "body_angle": body_angle, "watermark_angle": watermark_angle,
        "watermark_references": references,
        "raw_count": len(texts), "kept_count": len(keep),
        "watermark_removed": sum(x["reason"] != "empty_ocr_result" for x in removed),
        "empty_removed": sum(x["reason"] == "empty_ocr_result" for x in removed),
        "removed_blocks": removed,
    }
    filtered["watermark_filter"] = metadata
    return filtered
