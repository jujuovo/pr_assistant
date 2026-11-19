"""Template adapters for competition awards and the CSP transcript."""
import re

from .fields import AWARD, compact, dates, labeled, match, names


def award_certificate(key, lines):
    text = compact("".join(lines))
    markers = {
        "computer-design": "中国大学生计算机设计大赛",
        "software-design": "大学生软件设计大赛",
        "challenge-cup": "创业计划竞赛",
    }
    event = markers[key] if markers[key] in text else None
    if key == "software-design" and event and "中国软件杯" in text:
        event = "中国软件杯" + event
    if key == "challenge-cup" and event and "挑战杯" in text:
        event = "挑战杯" + event
    if not event:
        return {"event": None}, ("event",), ["样本与所选赛事的标题不匹配，请确认类别"]
    person_chars = r"([\u3400-\u9fff·、，,]{2,70})"
    students = (
        labeled(lines, r"^参赛学生", person_chars) if key == "computer-design" else
        labeled(lines, r"^(?:获奖)?同学", person_chars) if key == "software-design" else
        next((value for line in lines if (value := match("^" + person_chars + r"同学[:：]?$", line))), None)
    )
    title = match(r"《([^》]{2,160})》", text) or labeled(lines, r"^获奖项目", r"(.+)")
    award = match(f"({AWARD})", text)
    fields = {
        "event": event,
        "edition": match(r"(第[零〇一二三四五六七八九十百0-9]+届)", text),
        "participants": names(students),
        "project": title,
        "school": labeled(lines, r"^学校名称", r"(.+)"),
        "award": award,
        "stage_as_printed": match(r"(全国总决赛|省级赛|校级赛)", text),
        "group": match(r"(普通教育组|职业教育组)", text),
        "certificate_no": labeled(lines, r"^证书编号", r"^([a-z0-9-]{6,40})(?![a-z0-9-])"),
        "advisers": names(labeled(lines, r"^(?:指导教师|指导老师|寻老师)", person_chars)),
        "award_date": next(dates(text), None),
    }
    warnings = []
    if not award and "等奖" in text:
        warnings.append("奖项文字断裂，未自动拼接获奖等级")
    if any(re.fullmatch(r"1/[2-9]\d*", line) for line in lines):
        warnings.append("画面显示还有后续页面，请人工确认材料是否齐全")
    return fields, ("event", "participants", "project", "award"), warnings


def csp_transcript(lines):
    text = compact("".join(lines))
    if "CSP" not in text.upper() or not ("认证成绩" in text or "TRANSCRIPT" in text.upper()):
        return {"document_type": None}, ("document_type",), ["未发现 CSP 认证成绩单标识"]
    # Match the six numeric cells immediately after the total-score table header.
    score_row = None
    for index, line in enumerate(lines):
        if compact(line).upper() in {"TOTALSCORES", "总成绩"}:
            cells = lines[index + 1:index + 7]
            if len(cells) == 6 and all(re.fullmatch(r"\d{1,3}", cell) for cell in cells):
                values = list(map(int, cells))
                if all(0 <= n <= 100 for n in values[:5]) and sum(values[:5]) == values[5]:
                    score_row = values
                    break
    fields = {
        "document_type": "csp_transcript",
        "certificate_no": match(r"(CCF-IDEN-CSP-\d{4}-\d+)", text),
        "name": labeled(lines, r"^姓名(?:/NAME)?", r"^([\u3400-\u9fff·]{2,12})$"),
        "test_date": labeled(lines, r"^日期(?:/DATE)?", r"^(20\d{2}[./-]\d{1,2}[./-]\d{1,2})$"),
        "batch": labeled(lines, r"^批次(?:/BATCH)?", r"^(\d{1,4})$"),
        "language": labeled(lines, r"^编程语言(?:/PROG\.LAN)?", r"^([\w+/#+.-]+)$"),
        "test_site": labeled(lines, r"^认证点(?:/PLACE)?", r"(.+)"),
        "task_scores": score_row[:5] if score_row else None,
        "total_score": score_row[5] if score_row else None,
    }
    # Some templates split the bilingual date label across two OCR blocks.
    raw_date = fields["test_date"] or match(r"日期(?:/DATE)?[:：]?(20\d{2}[./-]\d{1,2}[./-]\d{1,2})", text)
    fields["test_date"] = next(dates(raw_date or ""), None)
    return fields, ("certificate_no", "name", "test_date", "total_score"), (
        [] if score_row else ["未定位到可核对的总分行，请查看原件"])
