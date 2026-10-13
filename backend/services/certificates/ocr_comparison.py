"""Compare recognized certificate fields; never silently overwrite disagreements."""
import re
from datetime import date


def extract_fields(texts):
    lines=[re.sub(r"\s+","",text) for text in texts if text.strip()]
    joined="".join(lines)
    fields={}
    field_labels = re.compile(r"学校名称|(?:学生|学)?姓名|指导老师|证件号码|证书编号")
    for key,label in (("school","学校名称"),("student","姓名"),("teacher","指导老师")):
        value=None
        for i,line in enumerate(lines):
            match=re.search(label+r"[:：]?(.*)$",line)
            if match:
                tail=match.group(1) or (lines[i+1] if i+1<len(lines) else "")
                # A following field label is not the missing value of this field.
                tail=field_labels.split(tail,maxsplit=1)[0]
                name=re.match(r"[\u4e00-\u9fff·]{2,10}",tail)
                if name:
                    value=name.group(0)
                    break
        fields[key]=value
    patterns={
        "edition":r"第[零一二三四五六七八九十百0-9]+届",
        "track":r"(?:C/C\+\+|Python|Java|C\+\+)程序设计",
        "group":r"(?:大学|学)[A-Za-z]组",
        "region":r"[\u4e00-\u9fff]{2}赛区",
        "award":r"特等奖|一等奖|二等奖|三等奖|优秀奖|优胜奖",
        "certificate_no":r"证书编号[:：]?(\d{6,20})",
        "date":r"\d{4}年\d{1,2}月\d{1,2}日",
    }
    for key,pattern in patterns.items():
        match=re.search(pattern,joined)
        fields[key]=(match.group(1) if key=="certificate_no" else match.group(0)) if match else None
    # Do not append a following OCR noise block (e.g. a lone 5) to an identifier.
    fields["certificate_no"] = None
    for i,line in enumerate(lines):
        label = re.search(r"证书编号[:：]?(.*)$",line)
        if label:
            tail = label.group(1)
            if not tail and i+1 < len(lines):
                tail = lines[i+1]
            number = re.fullmatch(r"(\d{6,20})[。.]?",tail)
            if number:
                fields["certificate_no"] = number.group(1)
                break
    return fields


def compare_ocr_fields(raw_texts,processed_texts):
    raw,processed=extract_fields(raw_texts),extract_fields(processed_texts)
    differences=[]
    for key in raw:
        if raw[key] and not processed[key]:
            differences.append({"field":key,"status":"lost_after_preprocessing","raw":raw[key],"processed":None})
        elif raw[key] and processed[key] and raw[key]!=processed[key]:
            differences.append({"field":key,"status":"disagreement","raw":raw[key],"processed":processed[key]})
    missing_fields = [key for key,value in processed.items() if not value]
    invalid_fields = []
    if processed["group"] and not processed["group"].startswith("大学"):
        invalid_fields.append("group")
    if processed["date"]:
        parts = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日",processed["date"])
        try:
            date(*(int(v) for v in parts.groups()))
        except (ValueError,AttributeError):
            invalid_fields.append("date")
    return {
        "raw_fields":raw,"processed_fields":processed,"differences":differences,
        "missing_fields":missing_fields,"invalid_fields":invalid_fields,
        "requires_manual_review":bool(differences or missing_fields or invalid_fields),
        "note":"Recognized values are provisional; watermark match is not authenticity verification.",
    }
