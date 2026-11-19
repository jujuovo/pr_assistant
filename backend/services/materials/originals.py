"""Recheck private originals before OCR-backed evidence is submitted or approved."""
from hashlib import sha256


def verify_ocr_originals(row):
    from material_models import CompetitionOcrJob
    from ocr_models import OCRMaterialLink
    # Editing can invalidate raw OCR but must never disable original integrity checks.
    has_ocr = isinstance(row.ocr_raw_terms,dict) or CompetitionOcrJob.query.filter_by(record_id=row.id).first() is not None or OCRMaterialLink.query.filter_by(material_record_id=row.id).first() is not None
    if not has_ocr:
        return
    from services.materials.service import stored_path
    from use_cases.materials import MaterialUseCaseError
    for item in row.attachments:
        try:
            digest, size = sha256(), 0
            with stored_path(item.stored_name).open("rb") as stream:
                for block in iter(lambda: stream.read(1024*1024), b""):
                    size += len(block)
                    if size > item.size:
                        raise ValueError()
                    digest.update(block)
            if size != item.size or digest.hexdigest() != item.sha256:
                raise ValueError()
        except (OSError, ValueError):
            raise MaterialUseCaseError("原件缺失或已发生变化，请重新上传并核对材料",
                                       code="original_integrity_failed",status_code=409) from None
