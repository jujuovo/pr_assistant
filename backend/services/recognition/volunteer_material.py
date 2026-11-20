"""Extract volunteer evidence, then apply the configured platform screen policy."""
import re
from decimal import Decimal
from datetime import date, datetime
from hashlib import sha256
from PIL import Image

LABELS = {
    "hours": r"(?:本次工时|志愿服务工时|服务时长|志愿时长|信用时数|荣誉时数|服务工时|工时|时数)",
    "award_date": r"(?:系统录入并审核通过日期|审核通过日期|审核通过时间|认定日期|录入时间|录入日期)",
}


def _lines(page):
    scores = page.get("rec_scores", [])
    return [{"text": re.sub(r"\s+", "", str(text)).replace("：", ":"),
             "confidence": float(scores[i]) if i < len(scores) else None}
            for i, text in enumerate(page.get("rec_texts", []))]


def _candidates(lines, label, value_pattern):
    found = []
    for i, line in enumerate(lines):
        anchor = re.search(label + r"[:：]?", line["text"])
        if not anchor:
            continue
        suffix = line["text"][anchor.end():]
        choices = [(suffix, line)] if suffix else [(item["text"], item) for item in lines[i+1:i+2]]
        for text, evidence in choices:
            match = re.match(value_pattern, text)
            if match:
                found.append((match.groups(), [line, evidence]))
    return found


def _single(candidates, convert):
    values, evidence = set(), []
    for groups, items in candidates:
        try:
            values.add(convert(groups))
            evidence.extend(items)
        except (ValueError, ArithmeticError):
            continue
    return (next(iter(values)) if len(values) == 1 else None), evidence


def filter_platform_noise(page):
    """Discard only extremely uncertain glyphs; retain every readable candidate."""
    scores = page.get("rec_scores", [])
    keep = [i for i in range(len(page.get("rec_texts", []))) if i >= len(scores) or float(scores[i]) >= .5]
    filtered = dict(page)
    for key in ("rec_texts", "rec_scores", "rec_boxes", "rec_polys"):
        values = page.get(key)
        if values is not None:
            filtered[key] = [values[i] for i in keep]
    return filtered


PLATFORM_POLICY_VERSION = "volunteer-screen-20261120-v1"


def platform_policy(platform, lines):
    """The page policy is distinct from text printed in the screenshot."""
    kind = platform.get("page_type")
    labels = {"credit": r"信用时数详情|时长详情", "honor": r"荣誉时数详情"}
    title = [line for line in lines if re.fullmatch(labels.get(kind, r"(?!)"), line["text"])]
    fields = platform["fields"]
    names = ("check_in", "check_out") if kind == "credit" else ("recorded_at",) if kind == "honor" else ()
    evidence = [item for name in names for item in fields[name]["evidence"]]
    day = None
    try:
        times = [datetime.fromisoformat(fields[name]["value"]) for name in names]
        if times and (len(times) == 1 or times[-1] >= times[0]):
            day = times[-1].date().isoformat()
    except (ValueError, TypeError):
        pass
    # A title alone is insufficient to establish the expected page layout.
    structure_valid = bool(title and names and all(fields[name]["evidence"] for name in names))
    policy = {"version": PLATFORM_POLICY_VERSION, "page_type": kind,
              "date_basis": "credit_check_out" if kind == "credit" else "honor_recorded_at" if kind == "honor" else None,
              "description": "信用时数与荣誉时数页面按普通志愿服务核对；信用按签到签退核对并取签退日期，荣誉取录入日期",
              "screen_matched": structure_valid}
    return ("regular" if structure_valid else None), day, title, evidence, policy


def extract(page, image_width=None):
    lines = _lines(page)
    hours, hours_evidence = _single(_candidates(lines, LABELS["hours"], r"([0-9]+(?:\.[0-9]+)?)(?:小时|h|$)"),
                                   lambda g: str(Decimal(g[0]).normalize()))
    award_date, date_evidence = _single(_candidates(lines, LABELS["award_date"],
        r"(20[0-9]{2})[年./-]([0-9]{1,2})[月./-]([0-9]{1,2})(?:日|$|[T0-9:])"),
        lambda g: date(*map(int, g)).isoformat())
    kinds = {"普通志愿服务": "regular", "普通工时": "regular", "常规志愿服务": "regular",
             "大型赛会": "reduced", "支教": "reduced", "大型赛会及支教": "reduced", "大型赛会或支教": "reduced"}
    label = r"(?:工时类别|工时类型|服务类别|服务类型|活动类别|活动类型)"
    candidates = _candidates(lines, label, r"(.+)$")
    candidates += [((line["text"],), [line]) for line in lines if line["text"] in kinds]
    type_hits = [((kinds[group[0]],), evidence) for group, evidence in candidates if group[0] in kinds]
    service_type, type_evidence = _single(type_hits, lambda g: g[0])
    platform = None
    baseline = None
    noise_filtered = False
    policy = None
    if image_width and any(re.search(r"信用时数详情|荣誉时数详情|时长详情", line["text"]) for line in lines):
        from .volunteer import extract as extract_platform
        platform = extract_platform(page, image_width)
        baseline = platform
        if platform["fields"]["displayed_hours"]["value"] is None and any(w["code"] == "ambiguous_hours" for w in platform["warnings"]):
            filtered = filter_platform_noise(page)
            if len(filtered["rec_texts"]) < len(page["rec_texts"]):
                platform = extract_platform(filtered, image_width)
                noise_filtered = True
        # Reuse the lab's coordinate extractor. Its missing fields stay missing;
        # a page title is not a label for the number printed in the centre.
        extracted = platform["fields"]["displayed_hours"]
        hours = str(Decimal(str(extracted["value"])).normalize()) if extracted["value"] is not None else None
        hours_evidence = extracted["evidence"]
        service_type, award_date, type_evidence, date_evidence, policy = platform_policy(platform, lines)
    fields = {"hours": hours, "service_type": service_type, "award_date": award_date}
    evidence = {"hours": hours_evidence, "service_type": type_evidence, "award_date": date_evidence}
    # Low-quality or ambiguous evidence is never treated as an exact match.
    missing = [name for name, value in fields.items() if value is None or any(
        item["confidence"] is None or item["confidence"] < .9 for item in evidence[name])]
    if platform:
        fields.update({name: item["value"] for name, item in platform["fields"].items() if name != "displayed_hours"})
    return {"fields": fields, "evidence": evidence, "platform_extraction": platform, "platform_baseline": baseline, "platform_policy": policy, "noise_filtered": noise_filtered, "missing_fields": missing,
            "ocr_model": "PP-OCRv5_mobile", "adapter_version": "volunteer-material-3",
            "status": "manual_review" if missing else "extracted", "images": {},
            "authenticity": "not_assessed", "requires_human_verification": True}


def recognize(provider, original):
    with Image.open(original) as image:
        width = image.width
        image.verify()
    result = extract(provider.predict(original), width)
    result["source_sha256"] = sha256(original.read_bytes()).hexdigest()
    return result
