"""从带坐标的 OCR 结果中提取志愿工时；不判断截图真实性。"""
import re
from datetime import datetime
from decimal import Decimal
from services.volunteer_rules import parse_number


def normalize(text):
    return re.sub(r"\s+", "", text).replace("：", ":").replace("＋", "+").replace("．", ".")


def make_lines(data):
    texts, scores = data.get("rec_texts", []), data.get("rec_scores", [])
    boxes = data.get("rec_boxes")
    polygons = data.get("rec_polys")
    lines = []
    for i, text in enumerate(texts):
        if boxes is not None and i < len(boxes):
            box = [float(v) for v in boxes[i]]
        elif polygons is not None and i < len(polygons):
            points = polygons[i]
            box = [min(p[0] for p in points), min(p[1] for p in points),
                   max(p[0] for p in points), max(p[1] for p in points)]
            box = [float(v) for v in box]
        else:
            raise ValueError("OCR 结果缺少文字坐标，无法可靠区分签到和签退列")
        lines.append({"text": str(text), "confidence": float(scores[i]) if i < len(scores) else 0.0,
                      "box": box})
    return lines


def cx(line):
    return (line["box"][0] + line["box"][2]) / 2


def cy(line):
    return (line["box"][1] + line["box"][3]) / 2


def field(value=None, evidence=()):
    evidence = list(evidence)
    return {"value": value, "ocr_confidence": min((x["confidence"] for x in evidence), default=None),
            "evidence": evidence}


def label(lines, word):
    matches = [x for x in lines if word in normalize(x["text"])]
    return max(matches, key=lambda x: x["confidence"], default=None)


def extract_datetime(lines, anchor, peer, page_width):
    if anchor is None:
        return field()
    # 同一列内按空间位置寻找日期和时间，避免串到另一列或状态栏。
    midpoint = (cx(anchor) + cx(peer)) / 2 if peer else page_width / 2
    left = cx(anchor) < midpoint
    candidates = [x for x in lines if cy(x) >= anchor["box"][1]
                  and ((cx(x) < midpoint) == left)]
    candidates.sort(key=lambda x: cy(x))
    date_hit = time_hit = None
    for item in candidates:
        text = normalize(item["text"])
        date_match = re.search(r"(20\d{2})[年/.-](\d{1,2})[月/.-](\d{1,2})日?", text)
        time_match = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?::(\d{2}))?(?!\d)", text)
        if date_match and date_hit is None:
            date_hit = (date_match, item)
        if time_match and time_hit is None:
            time_hit = (time_match, item)
        if date_hit and time_hit:
            break
    if not date_hit or not time_hit:
        return field()
    dm, dl = date_hit
    tm, tl = time_hit
    try:
        value = datetime(int(dm[1]), int(dm[2]), int(dm[3]), int(tm[1]), int(tm[2]), int(tm[3] or 0))
    except ValueError:
        return field(None, [dl, tl] if dl is not tl else [dl])
    return field(value.isoformat(), [dl, tl] if dl is not tl else [dl])


def extract_row(lines, word, row_words):
    """提取标签右侧内容，支持组织名、录入原因等多行字段。"""
    anchor = label(lines, word)
    if anchor is None:
        return field()
    height = max(1, anchor["box"][3] - anchor["box"][1])
    following = [label(lines, name) for name in row_words if name != word]
    lower = min((x["box"][1] for x in following if x and cy(x) > cy(anchor)), default=float("inf"))
    matches = [x for x in lines if x is not anchor and x["box"][0] > anchor["box"][2]
               and cy(x) >= cy(anchor) - height and cy(x) < lower]
    matches.sort(key=lambda x: (round(cy(x) / height), x["box"][0]))
    if matches:
        return field("".join(x["text"] for x in matches).strip(" >›〉"), matches)
    inline = normalize(anchor["text"]).split(word, 1)[-1].lstrip(":")
    return field(inline or None, [anchor] if inline else [])


def parse_recorded_at(value_field):
    if not value_field["value"]:
        return value_field
    text = normalize(value_field["value"])
    match = re.fullmatch(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
    if match:
        try:
            value = datetime(*[int(match[i]) for i in range(1, 6)], int(match[6] or 0))
            return field(value.isoformat(), value_field["evidence"])
        except ValueError:
            pass
    return field(None, value_field["evidence"])


def extract(data, image_width, claimed_hours=None, tolerance_minutes=1.0, confidence_threshold=0.90):
    lines = make_lines(data)
    warnings = []
    def warn(code, message):
        warnings.append({"code": code, "message": message})

    start_label, end_label = label(lines, "签到时间"), label(lines, "签退时间")
    honor_title = label(lines, "荣誉时数详情")
    title = honor_title or label(lines, "信用时数详情") or label(lines, "时长详情")
    page_type = "honor" if honor_title else "credit" if title else "unknown"
    time_labels = [x for x in (start_label, end_label) if x]
    upper_bound = min((x["box"][1] for x in time_labels), default=None)
    if honor_title:
        basic = label(lines, "基础信息")
        upper_bound = basic["box"][1] if basic else None
    # 时数在页面标题下、签到签退标签上；多候选时不擅自选一个。
    hour_candidates = []
    if title and upper_bound is not None:
        for item in lines:
            if not (cy(title) < cy(item) < upper_bound):
                continue
            match = re.fullmatch(r"\+?(\d+(?:\.\d+)?)\s*(?:小时|时数|h)?", normalize(item["text"]), re.I)
            if match and image_width * 0.25 < cx(item) < image_width * 0.75:
                hour_candidates.append((match[1], item))
    hours = field()
    if len(hour_candidates) == 1:
        value, evidence = hour_candidates[0]
        # 先验证原始小数，避免浮点转换吞掉超限精度或将极大数变成 Infinity。
        try:
            parsed = parse_number(value)
            hours = field(float(parsed), [evidence])
        except ValueError:
            hours = field(value, [evidence])
    elif len(hour_candidates) > 1:
        warn("ambiguous_hours", "时数区域有多个数字候选，需要人工选择")

    check_in = extract_datetime(lines, start_label, end_label, image_width)
    check_out = extract_datetime(lines, end_label, start_label, image_width)
    activity_anchor = label(lines, "参与活动")
    activity = field()
    if activity_anchor:
        row_height = max(1, activity_anchor["box"][3] - activity_anchor["box"][1])
        right = [x for x in lines if x["box"][0] > activity_anchor["box"][2]
                 and abs(cy(x) - cy(activity_anchor)) < row_height]
        right.sort(key=lambda x: x["box"][0])
        if right:
            activity = field("".join(x["text"] for x in right).strip(" >›〉"), right)
        else:
            inline = normalize(activity_anchor["text"]).split("参与活动", 1)[-1].lstrip(":")
            if inline:
                activity = field(inline, [activity_anchor])
    if activity["value"] and re.search(r"…|\.{2,}", activity["value"]):
        warn("activity_truncated", "活动名称被省略，不能据此确定完整活动身份")
    elif activity["value"] and any(x["box"][2] > image_width * 0.85 for x in activity["evidence"]):
        warn("activity_completeness_unverified", "活动文字接近页面右边界，可能省略或未完整识别；须与完整活动详情核对")

    fields = {"displayed_hours": hours, "check_in": check_in, "check_out": check_out,
              "activity_name": activity}
    required = list(fields)
    if honor_title:
        row_words = ["志愿者姓名", "录入人姓名", "录入组织名", "录入时间", "录入类型", "录入原因"]
        for key, word in zip(["volunteer_name", "recorder_name", "recording_organization", "recorded_at", "record_type", "record_reason"], row_words):
            fields[key] = extract_row(lines, word, row_words)
        fields["recorded_at"] = parse_recorded_at(fields["recorded_at"])
        # 荣誉补录页面没有签到签退或活动名称，这些字段为空属于不适用。
        required = ["displayed_hours", "volunteer_name", "recorder_name", "recording_organization",
                    "recorded_at", "record_type", "record_reason"]
        warn("honor_requires_policy_review", "荣誉时数需按学院政策人工确认是否计入志愿工时；录入时间不是活动发生时间")
        warn("duration_check_not_applicable", "该页面未提供签到签退，不进行活动持续时间核对")
    for key in required:
        item = fields[key]
        if item["value"] is None:
            warn("missing_" + key, f"未可靠提取字段：{key}")
        elif item["ocr_confidence"] is not None and item["ocr_confidence"] < confidence_threshold:
            warn("low_confidence_" + key, f"字段 {key} OCR 分数较低，需看原图确认")

    elapsed_seconds = elapsed_hours = difference_minutes = None
    if check_in["value"] and check_out["value"]:
        elapsed_seconds = int((datetime.fromisoformat(check_out["value"]) -
                               datetime.fromisoformat(check_in["value"])).total_seconds())
        if elapsed_seconds < 0:
            warn("invalid_time_order", "签退时间早于签到时间")
        else:
            elapsed_hours = elapsed_seconds / 3600
            if isinstance(hours["value"], (int, float)):
                difference_minutes = abs(elapsed_hours - hours["value"]) * 60
                if difference_minutes > tolerance_minutes:
                    warn("duration_difference", "截图时数与签到签退间隔差异超过实验容差；须核对平台计时规则")
    claim_match = None
    if claimed_hours is not None and hours["value"] is not None:
        claim_match = Decimal(str(claimed_hours)) == Decimal(str(hours["value"]))
        if not claim_match:
            warn("claim_mismatch", "申报时长与截图显示时数不一致")
    warn("identity_unverified", "此实验不验证截图是否属于申报学生")
    return {"page_type": page_type, "fields": fields, "checks": {"claimed_hours": claimed_hours, "claim_matches_display": claim_match,
            "elapsed_seconds": elapsed_seconds, "elapsed_hours": elapsed_hours,
            "display_vs_elapsed_difference_minutes": difference_minutes,
            "tolerance_minutes": tolerance_minutes}, "warnings": warnings,
            "recognition_status": "extracted" if all(fields[key]["value"] is not None for key in required) else "incomplete",
            "review_status": "pending_human_review", "authenticity": "not_verified"}
