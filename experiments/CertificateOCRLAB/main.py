"""Blue-bridge certificate OCR experiment with preserved evidence and isolated runs."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from time import perf_counter

from PIL import Image
from src.watermark_filter import filter_watermarks
from src.watermark_preprocess import prepare_watermark_image
from src.zigzag_preprocess import prepare_zigzag_image
from src.ocr_comparison import compare_ocr_fields, extract_fields

from src.lab_io import IMAGE_EXTENSIONS, OUTPUTS as OUTPUT_DIR, SAMPLES, file_sha256, save_json
from src.ocr_runtime import DEFAULT_BOX_THRESHOLD, DEFAULT_SIDE, create_paddle, prediction_options, validate_page

IMAGE_PATH = SAMPLES / "LanqiaoCup"


def parse_args():
    parser = argparse.ArgumentParser(description="蓝桥杯证书OCR、水印确认及ZigZag预处理")
    parser.add_argument("--input", type=Path, default=IMAGE_PATH, help="图片文件或目录，默认蓝桥杯样本")
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S_%f")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR/f"run_{stamp}", help="空结果目录，默认每次新建")
    parser.add_argument("--model", choices=("server", "mobile"), default="mobile")
    parser.add_argument("--no-watermark-filter", action="store_true")
    parser.add_argument("--watermark-text", action="append")
    parser.add_argument("--preprocess-watermark", action=argparse.BooleanOptionalAction, default=True,
                        help="默认检查蓝桥杯水印并去水印；其它模板需显式关闭或另行配置")
    parser.add_argument("--watermark-method", choices=("zigzag", "mask"), default="zigzag")
    parser.add_argument("--zigzag-size", type=int, default=30)
    parser.add_argument("--zigzag-weight", type=int, default=90)
    parser.add_argument("--zigzag-threshold-offset", type=int, default=0)
    parser.add_argument("--expected-watermark", default="蓝桥杯")
    parser.add_argument("--gray-min", type=int, default=180)
    parser.add_argument("--gray-max", type=int, default=245)
    parser.add_argument("--det-max-side", type=int, default=DEFAULT_SIDE)
    parser.add_argument("--det-box-thresh", type=float, default=DEFAULT_BOX_THRESHOLD)
    parser.add_argument("--cpu-threads", type=int, default=4)
    args = parser.parse_args()
    if args.zigzag_size <= 0:
        parser.error("zigzag-size必须大于0")
    if not 1 <= args.zigzag_weight <= 100:
        parser.error("zigzag-weight必须在1到100之间")
    if not -255 <= args.zigzag_threshold_offset <= 255:
        parser.error("zigzag-threshold-offset必须在-255到255之间")
    if not 0 <= args.gray_min < args.gray_max <= 255:
        parser.error("灰度阈值需满足0 <= gray-min < gray-max <= 255")
    if args.det_max_side is not None and args.det_max_side <= 0:
        parser.error("det-max-side必须大于0")
    if args.det_box_thresh is not None and not 0 <= args.det_box_thresh <= 1:
        parser.error("det-box-thresh必须在0到1之间")
    if args.cpu_threads <= 0:
        parser.error("cpu-threads必须大于0")
    if args.preprocess_watermark and not args.expected_watermark.strip():
        parser.error("预期水印文字不能为空")
    return args


def plan_inputs(args):
    """Validate inputs and avoid overwrite, stale results and same-stem collisions."""
    source, output = args.input.resolve(), args.output.resolve()
    if source.is_file():
        if source.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError("输入必须是支持的图片；当前不支持PDF")
        paths = [source]
    elif source.is_dir():
        paths = sorted((p.resolve() for p in source.iterdir()
                        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS), key=lambda p:p.name.casefold())
        if output.is_relative_to(source):
            raise ValueError("输出目录不能位于输入图片目录内")
    else:
        raise FileNotFoundError(f"输入不存在：{source}")
    if not paths:
        raise FileNotFoundError(f"没有图片：{source}")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError(f"输出目录已有内容，请使用新的空目录：{output}")
    counts = Counter(p.stem.casefold() for p in paths)
    used, plan = set(), []
    for path in paths:
        name = path.stem if counts[path.stem.casefold()] == 1 else f"{path.stem}__{path.suffix[1:].lower()}"
        if name.casefold() in used:
            name += "_"+hashlib.sha256(path.name.encode()).hexdigest()[:8]
        target = output/name
        if path.is_relative_to(target):
            raise ValueError("输出位置会包含或覆盖输入文件")
        used.add(name.casefold())
        plan.append((path,target))
    return plan


def run_ocr(ocr, path, target, options):
    target.mkdir(parents=True, exist_ok=True)
    pages = []
    start = perf_counter()
    for result in ocr.predict(str(path), **options):
        page = validate_page(result.json["res"])
        result.save_to_json(str(target))
        result.save_to_img(str(target))
        pages.append(page)
    if not pages:
        raise ValueError("OCR未返回任何页面")
    texts = [t for page in pages for t in page["rec_texts"]]
    (target/"ocr_text.txt").write_text("\n".join(texts), encoding="utf-8")
    return pages, round(perf_counter()-start,3)


def _prepare_watermark(args, raw_pages, original_copy, target):
    if len(raw_pages) != 1:
        prepared = None
        report = {"status":"uncertain", "watermark_status":"uncertain",
                  "expected_text":args.expected_watermark, "reason":"image_requires_single_page",
                  "requires_manual_review":True, "method":args.watermark_method,
                  "next_step":"manual_review"}
    else:
        with Image.open(original_copy) as source:
            image = source.convert("RGB")
        if args.watermark_method == "zigzag":
            prepared, mask, report = prepare_zigzag_image(
                image,raw_pages[0],expected=args.expected_watermark,
                size=args.zigzag_size,weight=args.zigzag_weight,
                threshold_offset=args.zigzag_threshold_offset)
        else:
            prepared, mask, report = prepare_watermark_image(
                image,raw_pages[0],expected=args.expected_watermark,
                gray_min=args.gray_min,gray_max=args.gray_max)
            report.update(watermark_status=report["status"], mask_filename="watermark_mask.png",
                          mask_type="eligible_pale_watermark_pixels")
        mask.save(target/report["mask_filename"])
    return prepared, report


def _save_filtered_pages(args, selected_pages, selected_path, target, row):
    for i,page in enumerate(selected_pages):
        refs = args.watermark_text or ([args.expected_watermark] if args.preprocess_watermark else None)
        filtered = page if args.no_watermark_filter else filter_watermarks(
            page,image_path=selected_path,watermark_texts=refs)
        row["filtered_texts"].extend(filtered["rec_texts"])
        row["filter_reports"].append(filtered.get("watermark_filter",{
            "raw_count":len(page["rec_texts"]),"kept_count":len(page["rec_texts"]),
            "watermark_removed":0,"empty_removed":0,"removed_blocks":[]}))
        suffix = "" if i==0 else f"_page{i+1}"
        save_json(target/f"filtered_result{suffix}.json",filtered)
    (target/"filtered_text.txt").write_text("\n".join(row["filtered_texts"]),encoding="utf-8")


def process_image(args, ocr, path, target, options):
    target.mkdir(parents=True, exist_ok=True)
    start = perf_counter()
    row = {
        "file":path.name, "output_subdir":target.name,
        "raw_texts":[], "processed_texts":[], "filtered_texts":[], "filter_reports":[],
        "automatic_ocr_after_removal":False, "processed_ocr_attempted":False,
        "requires_manual_review":True, "certificate_authenticity":"not_assessed",
    }
    stage = "copy_original"
    try:
        original_copy = target/("original"+path.suffix.lower())
        shutil.copy2(path,original_copy)
        row["source_sha256"] = file_sha256(original_copy)
        # Read one immutable evidence copy in both the OCR and image-processing paths.
        stage = "validate_image"
        with Image.open(original_copy) as source:
            source.verify()
        stage = "raw_ocr"
        print(f"检查原图：{path.name}", flush=True)
        raw_pages, seconds = run_ocr(ocr, original_copy, target/"raw", options)
        row["raw_ocr_seconds"] = seconds
        row["raw_texts"] = [t for p in raw_pages for t in p["rec_texts"]]
        row["raw_fields"] = extract_fields(row["raw_texts"])
        (target/"raw_text.txt").write_text("\n".join(row["raw_texts"]),encoding="utf-8")
        selected_pages, selected_path = raw_pages, original_copy
        if args.preprocess_watermark:
            stage = "watermark_preprocessing"
            prepared, report = _prepare_watermark(args, raw_pages, original_copy, target)
            row["watermark_check"] = report
            save_json(target/"watermark_check.json",report)
            if prepared is None:
                row["status"] = "manual_review"
                return row
            selected_path = target/"processed.png"
            prepared.save(selected_path)
            print(f"水印匹配；使用{args.watermark_method}修改{report['changed_pixels']}个像素；再次OCR",flush=True)
            stage = "processed_ocr"
            row["processed_ocr_attempted"] = True
            selected_pages,seconds = run_ocr(ocr,selected_path,target/"processed",options)
            row["processed_ocr_seconds"] = seconds
            row["processed_texts"] = [t for p in selected_pages for t in p["rec_texts"]]
            row["automatic_ocr_after_removal"] = True
            comparison = compare_ocr_fields(row["raw_texts"],row["processed_texts"])
        else:
            comparison = compare_ocr_fields(row["raw_texts"],row["raw_texts"])
        row["ocr_comparison"] = comparison
        row["requires_manual_review"] = comparison["requires_manual_review"]
        save_json(target/"ocr_comparison.json",comparison)
        stage = "text_filtering"
        _save_filtered_pages(args, selected_pages, selected_path, target, row)
        row["status"] = "manual_review" if row["requires_manual_review"] else "recognized"
        return row
    except Exception as exc:
        row.update(status="failed",error_stage=stage,error=str(exc),requires_manual_review=True)
        print(f"{path.name}处理失败（{stage}）：{exc}",flush=True)
        return row
    finally:
        row["elapsed_seconds"] = round(perf_counter()-start,3)
        save_json(target/"result.json",row)


def main():
    args = parse_args()
    plan = plan_inputs(args)
    args.output = args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=True)
    marker = args.output/"run.json"
    run_state = {"status":"starting","pid":os.getpid(),"input":str(args.input.resolve()),
                 "output":str(args.output),"method":args.watermark_method}
    # Exclusive creation reserves the destination even while model loading is in progress.
    with marker.open("x",encoding="utf-8") as handle:
        json.dump(run_state,handle,ensure_ascii=False,indent=2)
    print(f"加载PP-OCRv5 {args.model}模型……",flush=True)
    start = perf_counter()
    try:
        ocr = create_paddle(args.model, args.cpu_threads)
    except Exception as exc:
        run_state.update(status="startup_failed",error=str(exc))
        save_json(marker,run_state)
        raise
    run_state["status"] = "running"
    save_json(marker,run_state)
    options = prediction_options(args.det_max_side, args.det_box_thresh)
    summary = {
        "model":args.model, "device":"cpu", "enable_mkldnn":False, "cpu_threads":args.cpu_threads,
        "load_seconds":round(perf_counter()-start,3), "predict_options":options,
        "image_preprocessing_enabled":args.preprocess_watermark,
        "expected_watermark":args.expected_watermark, "watermark_method":args.watermark_method,
        "zigzag_parameters":{"mode":"color","backend":"cpu","size":args.zigzag_size,
                             "weight":args.zigzag_weight,"threshold_offset":args.zigzag_threshold_offset},
        "gray_min":args.gray_min,"gray_max":args.gray_max,
        "output_directory":str(args.output), "results":[],
    }
    for path,target in plan:
        summary["results"].append(process_image(args,ocr,path,target,options))
        summary["failed_images"] = sum(r["status"]=="failed" for r in summary["results"])
        save_json(args.output/"summary.json",summary)
    run_state.update(status="completed_with_errors" if summary["failed_images"] else "completed",
                     failed_images=summary["failed_images"])
    save_json(marker,run_state)
    print(f"完成：{args.output}",flush=True)
    return 1 if summary["failed_images"] else 0


if __name__=="__main__":
    raise SystemExit(main())
