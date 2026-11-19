"""Shared bounded multipart validation for material originals."""
from pathlib import Path


def prepare_uploads(files, limit, existing_count=0):
    if not 1 <= len(files) <= 10 or existing_count+len(files)>10:
        raise ValueError("每条材料最多10个附件")
    result=[]
    for file in files:
        name=Path((file.filename or '').replace(chr(92),'/')).name
        if (not name or len(name)>255 or any(ord(c)<32 or ord(c)==127 or 0xD800<=ord(c)<=0xDFFF for c in name)
            or Path(name).suffix.lower() not in ('.pdf','.jpg','.jpeg','.png','.webp','.csv','.xlsx')):
            raise ValueError("附件仅支持PDF、图片、CSV、XLSX")
        payload=file.stream.read(limit+1)
        if not payload or len(payload)>limit:
            raise ValueError("每个附件必须为非空且不超过10MB")
        result.append((name,payload))
    return result
