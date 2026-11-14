"""Evaluate saved ZigZag results; no model inference and no experiment-folder dependency."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from src.ocr_comparison import extract_fields

from src.lab_io import ROOT, file_sha256, load_json, save_json


def latest_output():
    candidates = []
    for path in (ROOT/"outputs").glob("*/summary.json"):
        try:
            data = load_json(path)
            marker = path.parent/"run.json"
            if marker.is_file():
                state=load_json(marker)
                if not isinstance(state,dict) or state.get("status") not in ("completed","completed_with_errors"):
                    continue
            if isinstance(data,dict) and data.get("image_preprocessing_enabled") and data.get("watermark_method")=="zigzag":
                candidates.append(path)
        except (OSError,ValueError):
            continue
    if not candidates:
        raise FileNotFoundError("没有 ZigZag 结果，请先运行 main.py")
    return max(candidates,key=lambda p:p.stat().st_mtime_ns).parent


def require(condition,message):
    if not condition:
        raise ValueError(message)


def contained_path(base, relative):
    require(isinstance(relative,(str,Path)),"结果路径格式不正确")
    base=base.resolve()
    path=(base/relative).resolve()
    require(path!=base and path.is_relative_to(base),"结果路径超出指定目录")
    return path


def evaluate(output, expected_path=None):
    output=output.resolve()
    summary=load_json(output/"summary.json")
    require(summary["image_preprocessing_enabled"] and summary["watermark_method"]=="zigzag",
            "评估器需要 ZigZag 预处理结果")
    expected = load_json(expected_path) if expected_path is not None else {}
    reference_path = ROOT / "tests/fixtures/zigzag_reference.json"
    reference = load_json(reference_path) if reference_path.is_file() else {}
    rows=[]
    for row in summary["results"]:
        target=contained_path(output,row.get("output_subdir",Path(row["file"]).stem))
        result={"file":row["file"],"requires_manual_review":row["requires_manual_review"],
                "status":row.get("status"),"original_copy_sha256_verified":None}
        original_copy=contained_path(target,"original"+Path(row["file"]).suffix.lower())
        if row.get("source_sha256"):
            require(original_copy.is_file(),"原始证据副本缺失")
            require(file_sha256(original_copy)==row["source_sha256"],
                    "原始证据副本哈希不一致")
            result["original_copy_sha256_verified"]=True
        check=row.get("watermark_check",{})
        result["watermark_status"]=check.get("watermark_status",check.get("status","not_checked"))
        if not row.get("automatic_ocr_after_removal") or row.get("status")=="failed":
            result.update(skipped=True,reason=row.get("error") or check.get("reason","incomplete_processing"))
            rows.append(result)
            continue
        raw_fields,processed_fields=extract_fields(row["raw_texts"]),extract_fields(row["processed_texts"])
        ref=expected.get(row["file"])
        checks={} if ref is None else {
            k:{"expected":v,"raw":raw_fields[k],"processed":processed_fields[k],
               "raw_exact":raw_fields[k]==v,"processed_exact":processed_fields[k]==v} for k,v in ref.items()}
        with Image.open(original_copy) as source:
            raw_img=np.asarray(source.convert("RGB"))
        with Image.open(contained_path(target,"processed.png")) as source:
            out_img=np.asarray(source.convert("RGB"))
        with Image.open(contained_path(target,"pixel_change_mask.png")) as source:
            mask=np.asarray(source.convert("L"))>0
        require(raw_img.shape==out_img.shape,"处理图尺寸改变")
        changed=np.any(raw_img!=out_img,axis=2)
        require(np.array_equal(changed,mask),"变化像素图与实际处理结果不一致")
        require(int(changed.sum())==check["changed_pixels"],"变化像素计数不一致")
        prior=reference.get(row["file"])
        same=None
        if prior and prior["source_sha256"]==row["source_sha256"]:
            parameters=check["parameters"]
            if all(parameters.get(k)==v for k,v in prior["parameters"].items()):
                same=hashlib.sha256(out_img.tobytes()).hexdigest()==prior["processed_rgb_sha256"]
        result.update(reference_available=ref is not None,
                      raw_exact_fields=sum(c["raw_exact"] for c in checks.values()) if ref else None,
                      processed_exact_fields=sum(c["processed_exact"] for c in checks.values()) if ref else None,
                      total_fields=len(checks), checks=checks,
                      matches_previous_zigzag_pixels=same,
                      changed_pixels=int(changed.sum()),changed_fraction=float(changed.mean()),
                      dark_ink_whitened_fraction=check["dark_ink_whitened_fraction"],
                      red_color_retention=check["red_color_retention"],
                      raw_ocr_seconds=row["raw_ocr_seconds"],processed_ocr_seconds=row["processed_ocr_seconds"],
                      preprocess_seconds=check["preprocess_seconds"],
                      conflict_fields=[d["field"] for d in row["ocr_comparison"]["differences"]],
                      missing_fields=row["ocr_comparison"].get("missing_fields",[]),
                      invalid_fields=row["ocr_comparison"].get("invalid_fields",[]))
        rows.append(result)
    return {"method":"Exact structured fields versus manual labels; not authenticity or generalization accuracy",
            "output_directory":str(output),"results":rows}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,help="结果目录，默认最近一次 ZigZag 运行")
    parser.add_argument("--expected", type=Path, help="本地人工标注 JSON（可选）")
    args=parser.parse_args()
    output=args.output.resolve() if args.output else latest_output()
    local_expected = ROOT / "tests/fixtures/lanqiao_expected.json"
    expected = args.expected or (local_expected if local_expected.is_file() else None)
    evaluation = evaluate(output, expected)
    save_json(output/"evaluation.json", evaluation)
    lines=["# ZigZag 实验复测报告","",
           "直接评估已保存结果；核验原图副本 SHA256、处理尺寸、像素变化图及独立参考哈希。","",
           "| 样本 | 水印状态 | 原图正确字段 | 处理图正确字段 | 与此前处理图一致 |",
           "|---|---|---:|---:|---|"]
    for row in evaluation["results"]:
        if row.get("skipped"):
            lines.append(f"| {row['file']} | {row['watermark_status']} | — | 未完成，需人工 | — |")
        elif not row["reference_available"]:
            lines.append(f"| {row['file']} | {row['watermark_status']} | 无人工标注 | 无人工标注 | {row['matches_previous_zigzag_pixels']} |")
        else:
            lines.append(f"| {row['file']} | {row['watermark_status']} | {row['raw_exact_fields']}/{row['total_fields']} | {row['processed_exact_fields']}/{row['total_fields']} | {row['matches_previous_zigzag_pixels']} |")
    lines+=["","关键字段缺失、格式异常或两次 OCR 冲突均要求人工复核。ZigZag 辅助图可能改变边框、笔画和颜色，证据审核看原始证书。",
            "","两张同版式样本不足以代表实际使用准确率；本实验未核验真实性，也未自动计算加分。"]
    (output/"复测报告.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    for row in evaluation["results"]:
        print(json.dumps({k:row[k] for k in ("file","raw_exact_fields","processed_exact_fields","matches_previous_zigzag_pixels","skipped") if k in row},ensure_ascii=False))
    print(f"评估完成：{output}")


if __name__=="__main__":
    main()
