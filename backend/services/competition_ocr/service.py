"""One image in; structured OCR suggestions and review flags out."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageOps, UnidentifiedImageError

from services.certificates.pipeline import predict as predict_page
from services.certificates.ocr_comparison import compare_ocr_fields, extract_fields
from services.certificates.zigzag_preprocess import prepare_zigzag_image
from .artifacts import ImageArtifacts
from .catalog import IMAGE_EXTENSIONS, category
from .engine import PaddleEngine
from .events import award_certificate, csp_transcript
from .fields import compact
from .materials import other_document, social_practice

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 24_000_000
FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}


def _decode(payload):
    if not 0 < len(payload) <= MAX_BYTES:
        raise ValueError("图片须非空且不超过 10 MB")
    try:
        with Image.open(BytesIO(payload)) as image:
            if image.format not in FORMATS or getattr(image, "n_frames", 1) != 1:
                raise ValueError("仅支持 JPEG、PNG、WebP、BMP、TIFF 单帧图片")
            if image.width * image.height > MAX_PIXELS or min(image.size) < 120:
                raise ValueError("图片尺寸不合格：最短边至少 120 像素，总像素不超过 2400 万")
            return ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ValueError("无法读取图片，请重新上传") from exc


def _predict(engine, path):
    return predict_page(engine, path)


def _lanqiao(image, page, engine, scratch, artifacts):
    raw = page["rec_texts"]
    processed, mask, watermark = prepare_zigzag_image(image, page, expected="蓝桥杯", size=30, weight=90)
    meta = {"watermark": watermark.get("status"), "ocr_passes": 1}
    if processed is None:
        return extract_fields(raw), ("student", "award", "certificate_no"), ["水印未通过检查，保留原图识别并转人工复核"], meta
    processed_path = scratch / "processed.png"
    processed.save(processed_path)
    second = _predict(engine, processed_path)
    if artifacts:
        artifacts.save_image("processed", processed)
        artifacts.save_image("pixel_change_mask", mask)
        artifacts.overlay("processed_ocr", processed, second)
    comparison = compare_ocr_fields(raw, second["rec_texts"])
    meta["ocr_passes"] = 2
    meta["differences"] = comparison["differences"]
    warnings = [f"处理前后不一致：{item['field']}" for item in comparison["differences"]]
    warnings += [f"字段缺失或格式异常：{key}" for key in comparison["missing_fields"] + comparison["invalid_fields"]]
    return comparison["processed_fields"], tuple(comparison["processed_fields"]), warnings, meta


def _extract(key, page):
    lines = [compact(text) for text in page["rec_texts"]]
    if key == "csp":
        return csp_transcript(lines)
    if key == "social-practice":
        polygons = page.get("rec_polys")
        if hasattr(polygons, "tolist"):
            polygons = polygons.tolist()
        return social_practice(lines, polygons if polygons is not None else [])
    if key == "other":
        return other_document(lines)
    return award_certificate(key, lines)


class CompetitionOCR:
    def __init__(self, engine=None):
        self.engine = PaddleEngine() if engine is None else engine

    def recognize(self, image_path, key, *, image_dir=None):
        path = Path(image_path)
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError("请输入支持的图片文件")
        with path.open("rb") as source:
            payload = source.read(MAX_BYTES + 1)
        return self._recognize(payload, key, image_dir, path.suffix.lower())

    def recognize_bytes(self, payload, key):
        return self._recognize(payload, key, None, None)

    def _recognize(self, payload, key, image_dir, suffix):
        spec = category(key)
        image = _decode(payload)
        artifacts = ImageArtifacts(image_dir) if image_dir is not None else None
        if artifacts:
            artifacts.original(payload, suffix)
        with TemporaryDirectory(prefix="certificate-ocr-") as directory:
            scratch = Path(directory)
            original = scratch / "original.png"
            image.save(original)
            page = _predict(self.engine, original)
            if artifacts:
                artifacts.overlay("raw_ocr", image, page)
            meta = {"ocr_passes": 1}
            if key == "lanqiao":
                fields, required, warnings, meta = _lanqiao(image, page, self.engine, scratch, artifacts)
            else:
                fields, required, warnings = _extract(key, page)
        if artifacts:
            meta["images"] = artifacts.files
        missing = [field for field in required if fields.get(field) in (None, "", [])]
        if missing:
            warnings.append("请核对缺失字段：" + "、".join(missing))
        return {
            "category": key, "category_name": spec.name, "material_kind": spec.kind,
            "status": "manual_review" if warnings else "extracted",
            "fields": fields, "missing_fields": missing, "warnings": warnings,
            "source_sha256": sha256(payload).hexdigest(), "authenticity": "not_assessed",
            "requires_human_verification": True, **meta,
        }
