"""真实图片/PDF → 原图 OCR → 蓝桥杯水印门控 → ZigZag → 第二次 OCR。"""
import hashlib
import json
import math
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageOps
from .ocr_comparison import extract_fields, compare_ocr_fields
from .zigzag_preprocess import prepare_zigzag_image
from .service import contained


def json_safe(data):
    return json.loads(json.dumps(data, ensure_ascii=False, allow_nan=False, default=lambda v: v.tolist()))


def predict(provider, path):
    predictor = getattr(provider, "predict_certificate", provider.predict)
    data = json_safe(predictor(path))
    texts, scores = data.get("rec_texts"), data.get("rec_scores")
    if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
        raise ValueError("OCR 文本结构无效")
    if not isinstance(scores, list) or len(scores) != len(texts) or any(
            not isinstance(s, (float, int)) or not math.isfinite(s) or not 0 <= s <= 1 for s in scores):
        raise ValueError("OCR 置信度结构无效")
    return data


def quality(image, max_pixels):
    if image.width * image.height > max_pixels:
        return {"acceptable": False, "reason": "图片像素过大，请压缩后重新上传"}
    if min(image.size) < 480:
        return {"acceptable": False, "reason": "图片分辨率过低，请上传清晰原图"}
    thumbnail = image.copy()
    thumbnail.thumbnail((1600, 1600))
    gray = cv2.cvtColor(np.asarray(thumbnail.convert("RGB")), cv2.COLOR_RGB2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return {"acceptable": sharpness >= 10, "width": image.width, "height": image.height,
            "sharpness": round(sharpness, 3), "reason": "" if sharpness >= 10 else "图片模糊或缺少有效文字，请重新上传"}


def pages_from(path, max_pixels, max_pages):
    if path.suffix.lower() == ".pdf":
        import pypdfium2 as pdfium
        with pdfium.PdfDocument(path) as document:
            if not 1 <= len(document) <= max_pages:
                raise ValueError(f"自动辅助仅支持1至{max_pages}页PDF，请拆分或人工核验")
            for i in range(len(document)):
                page = document[i]
                try:
                    width, height = page.get_size()
                    scale = min(150 / 72, 2400 / max(width, height))
                    if width * height * scale * scale > max_pixels:
                        raise ValueError("PDF页面像素过大")
                    bitmap = page.render(scale=scale)
                    try:
                        yield bitmap.to_pil().convert("RGB").copy()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
    elif path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
        with Image.open(path) as image:
            if image.width * image.height > max_pixels or getattr(image, "n_frames", 1) != 1:
                raise ValueError("图片过大或包含多帧，请重新上传单张证书")
            yield ImageOps.exif_transpose(image).convert("RGB").copy()
    else:
        raise ValueError("该附件格式不支持自动辅助，请上传图片/PDF或人工核验")


def process_page(image, folder, provider, claims, max_pixels):
    report = {"status": "manual_review", "authenticity": "not_assessed", "requires_manual_review": True,
              "quality": quality(image, max_pixels), "artifacts": {}, "warnings": []}
    original = folder / "original.png"
    image.save(original)
    report["artifacts"]["original"] = str(original.name)
    if not report["quality"]["acceptable"]:
        report.update(status="needs_reupload", message=report["quality"]["reason"])
        return report
    raw = predict(provider, original)
    report["raw_fields"] = extract_fields(raw["rec_texts"])
    report["raw_texts"], report["raw_scores"] = raw["rec_texts"], raw["rec_scores"]
    (folder / "raw_ocr.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    report["artifacts"]["raw_ocr"] = "raw_ocr.json"
    processed, mask, watermark = prepare_zigzag_image(image, raw, expected="蓝桥杯", size=30, weight=90)
    # 不向浏览器暴露部署机器的绝对文件路径。
    if "source" in watermark:
        watermark["source"].pop("path", None)
    report["watermark"] = json_safe(watermark)
    if processed is None:
        report["message"] = "水印缺失、不匹配、无法确定或处理异常，转人工核验。"
        report["warnings"].append({"code": "watermark_gate", "message": report["message"]})
        return report
    output = folder / "processed.png"
    processed.save(output)
    mask.save(folder / "pixel_change_mask.png")
    report["artifacts"].update(processed="processed.png", pixel_change_mask="pixel_change_mask.png")
    second = predict(provider, output)
    (folder / "processed_ocr.json").write_text(json.dumps(second, ensure_ascii=False, indent=2), encoding="utf-8")
    report["artifacts"]["processed_ocr"] = "processed_ocr.json"
    comparison = compare_ocr_fields(raw["rec_texts"], second["rec_texts"])
    report.update(comparison)
    report["processed_texts"], report["processed_scores"] = second["rec_texts"], second["rec_scores"]
    for difference in comparison["differences"]:
        report["warnings"].append({"code": "ocr_disagreement", "message": f"字段 {difference['field']} 在处理前后识别不一致，请核对原图"})
    for field in comparison["missing_fields"] + comparison["invalid_fields"]:
        report["warnings"].append({"code": "incomplete_field", "message": f"字段 {field} 缺失或格式异常"})
    for field in ("student", "award", "region", "group", "track"):
        claimed, extracted = claims.get(field), comparison["processed_fields"].get(field)
        if claimed and extracted and claimed != extracted:
            report["warnings"].append({"code": "claim_mismatch", "field": field,
                                       "claimed": claimed, "recognized": extracted,
                                       "message": f"申报的 {field} 与识别结果不一致，请人工核对"})
    report["requires_manual_review"] = bool(report["requires_manual_review"] or report["warnings"])
    report["status"] = "manual_review" if report["requires_manual_review"] else "recognized"
    report["message"] = "识别完成，存在待核对项。" if report["requires_manual_review"] else "识别完成，仍需教师核验原件和官方记录。"
    return report


def process_sources(sources, root, token, provider, claims, config, heartbeat=lambda: None):
    results = []
    max_pixels = config.get("CERTIFICATE_MAX_PIXELS", 20_000_000)
    max_pages = config.get("CERTIFICATE_MAX_PDF_PAGES", 4)
    work = contained(root, token)
    work.mkdir(parents=True, exist_ok=False)
    for source_index, source in enumerate(sources):
        path = contained(root, source["relative"])
        try:
            if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
                raise ValueError("原件快照校验失败，必须重新上传")
            for page_index, image in enumerate(pages_from(path, max_pixels, max_pages)):
                heartbeat()
                folder = work / f"file-{source_index}-page-{page_index}"
                folder.mkdir()
                try:
                    result = process_page(image, folder, provider, claims, max_pixels)
                except Exception as exc:
                    result = {"status": "failed", "authenticity": "not_assessed", "requires_manual_review": True,
                              "message": "识别失败，请重试或人工核验", "error": str(exc)[:1000], "artifacts": {}}
                result.update(filename=source["name"], page=page_index + 1, sha256=source["sha256"])
                result["artifacts"] = {k: str((folder / v).relative_to(root)).replace("\\", "/") for k, v in result["artifacts"].items()}
                result["artifacts"]["source"] = source["relative"]
                results.append(result)
                heartbeat()
        except Exception as exc:
            results.append({"filename": source["name"], "status": "manual_review", "requires_manual_review": True,
                            "message": str(exc)[:1000], "artifacts": {"source": source["relative"]}})
    statuses = {r["status"] for r in results}
    status = ("needs_reupload" if "needs_reupload" in statuses else "failed" if "failed" in statuses
              else "manual_review" if "manual_review" in statuses else "recognized")
    return json_safe({"status": status, "pages": results, "ocr_model": "PP-OCRv5_mobile",
                      "preprocessor": "ZigZag CPU color size=30 weight=90", "adapter_version": "lanqiao-1",
                      "authenticity": "not_assessed", "message": "识别只提供核对依据，不自动认定真实性或修改加分。"})
