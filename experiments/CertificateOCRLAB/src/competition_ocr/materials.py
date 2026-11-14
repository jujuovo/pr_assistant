"""Non-competition adapters for practice and miscellaneous evidence."""
import re

from .fields import compact, dates, match, names


def _platform_fields(lines, polygons):
    labels = {"提交人": "submitter", "表彰名称": "honor_name", "相关实践经历": "practice",
              "表彰信息": "honor_description", "表彰时间": "honor_date"}
    fields = dict.fromkeys(labels.values())
    if len(lines) != len(polygons):
        return fields
    boxes = [(min(pt[0] for pt in poly), min(pt[1] for pt in poly),
              max(pt[0] for pt in poly), max(pt[1] for pt in poly)) if poly else None for poly in polygons]
    anchors = [(index, boxes[index]) for index, line in enumerate(lines) if line in labels and boxes[index]]
    for index, (left, top, right, bottom) in anchors:
        height = max(1, bottom - top)
        mid = (top + bottom) / 2
        neighbors = [abs((b[1] + b[3]) / 2 - mid) for i, b in anchors if i != index]
        span = min([height * 1.5, *(d * .49 for d in neighbors)])
        candidates = []
        for line, box in zip(lines, boxes):
            if box and line and line not in labels and box[0] > right - height / 2:
                center = (box[1] + box[3]) / 2
                if abs(center - mid) <= span:
                    candidates.append((center, box[0], line))
        fields[labels[lines[index]]] = "".join(v for _, _, v in sorted(candidates)) or None
    fields["honor_date"] = next(dates(fields["honor_date"] or ""), None)
    return fields


def social_practice(lines, polygons):
    text = compact("".join(lines))
    team_names = re.findall(r"[“「]([^”」]{1,60})[”」]\s*实践队", text)
    team_names = list(dict.fromkeys(team_names))
    if "项目审核" in text and "社会实践" in text:
        fields = {"document_type": "platform_screenshot", **_platform_fields(lines, polygons)}
        fields["review_status_as_printed"] = match(r"(待系内审核|待学院审核|审核通过|审核驳回)", text)
        return fields, ("submitter", "honor_name", "honor_date"), [
            "截图只反映页面上显示的状态，请通过学校平台核验"]
    if "优秀团队名单" in text or (len(team_names) >= 3 and any("学院" in line for line in lines)):
        return {"document_type": "team_list", "teams": team_names}, ("teams",), [
            "仅提取当前截图中的可见队名，队名匹配不能证明个人参与"]
    if "实践" in text and ("证明" in text or "兹证明" in text):
        fields = {
            "document_type": "practice_proof",
            "team": team_names[0] if team_names else match(r"([\u3400-\u9fff]{2,50}实践队)(?:[（(:：]|一行)", text),
            "period_as_printed": match(r"(20\d{2}年(?:\d{1,2}月(?:至(?:20\d{2}年)?\d{1,2}月)?|寒假|暑假))", text),
            "issuer": match(r"(厦门大学招生(?:与)?考试办公室)", text),
            "members": names(match(r"实践队成员名单[:：]([^。]{1,250}?)(?:特此证明|。|$)", text)),
            "issue_date": next(dates(text), None),
        }
        return fields, ("team", "period_as_printed"), ["名单可能不完整，请核对原件及学校平台"]
    return {"document_type": None}, ("document_type",), ["无法判定为已适配的社会实践材料"]


def other_document(lines):
    text = compact("".join(lines))
    if "任职证明" in text:
        role = re.search(r"于(20\d{2}年\d{1,2}月)至(20\d{2}年\d{1,2}月)担任(.{2,45}?)(社长|会长|主席|部长|干事)[。！]", text)
        return {
            "document_type": "appointment_proof",
            "name": match(r"([\u3400-\u9fff]{2,6})同学[:：]", text),
            "start_month": role[1] if role else None, "end_month": role[2] if role else None,
            "organization": role[3] if role else None, "position": role[4] if role else None,
        }, ("name", "organization", "position"), ["任职证明不等同于考核结果"]
    if "成果证明报告" in text or "期刊分区" in text:
        return {
            "document_type": "research_report",
            "report_no": match(r"编号[:：]([A-Z0-9-]+)", text),
            "requester_school": match(r"委托者单位[:：]([^：:]{2,50}?)(?:检索数据库|$)", text),
            "database": match(r"检索数据库[:：]([^：:]{2,80}?)(?:经检索|$)", text),
            "publication_year": match(r"年份[:：]?(20\d{2})", text),
        }, ("report_no", "database"), ["检索报告不用于自动判断论文归属、分区或加分"]
    return {"document_type": None}, ("document_type",), ["其他材料未匹配到已适配的版式"]
