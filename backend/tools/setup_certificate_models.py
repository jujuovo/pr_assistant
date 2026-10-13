"""下载/复制官方模型到主项目；没有实验程序路径依赖。"""
import hashlib
import json
import os
from pathlib import Path
import shutil


def main():
    os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK','True')
    root=Path(os.environ.get('OCR_MODEL_ROOT',Path(__file__).resolve().parents[1]/'ocr-models'))
    names=('PP-OCRv5_mobile_det','PP-OCRv5_mobile_rec')
    cache=Path.home()/'.paddlex/official_models'
    if any(not (cache/name/'inference.yml').is_file() for name in names):
        from paddleocr import PaddleOCR
        PaddleOCR(device='cpu',enable_mkldnn=False,text_detection_model_name=names[0],text_recognition_model_name=names[1],
                  use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False)
    for name in names:
        shutil.copytree(cache/name,root/name,dirs_exist_ok=True)
    manifest={str(path.relative_to(root)).replace('\\','/'):hashlib.sha256(path.read_bytes()).hexdigest()
              for name in names for path in (root/name).rglob('*') if path.is_file()}
    (root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'主项目模型已准备：{root}（{len(manifest)}个文件）')


if __name__=='__main__':
    main()
