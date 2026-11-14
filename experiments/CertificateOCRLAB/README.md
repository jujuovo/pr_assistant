# CertificateOCRLAB

本地图片 OCR 实验。按材料类别提取结构化字段，返回缺失字段和复核提示；结果不认定真实性或加分。

| 位置 | 用途 |
| --- | --- |
| src/competition_ocr/ | 分类目录、OCR 引擎、字段适配器、Python/HTTP 接口和命令行 |
| src/ | 原蓝桥杯水印检测、ZigZag 调用、两次 OCR 对照 |
| samples/ | 分类原图；index.json 保存来源、文件大小及 SHA-256 |
| tests/ | 接口与适配器回归、旧流程测试和人工参考字段 |
| docs/ | 接口说明、蓝桥杯旧流程说明 |
| third_party/zigzag/ | 原有第三方源码与许可证 |
| outputs/、archive/ | 实验输出与历史归档 |

在本实验目录创建 Python 3.13 环境：

    py -3.13 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt

将测试图按 [样本目录表](samples/README.md) 分类放置。未提供本地样本清单时，单元测试仅跳过样本摘要校验。

在本实验目录执行 PowerShell 命令：

    .\.venv\Scripts\python.exe -B -m src.competition_ocr categories
    .\.venv\Scripts\python.exe -B -m src.competition_ocr recognize csp '图片路径'
    .\.venv\Scripts\python.exe -B -m src.competition_ocr samples all --save-images --output outputs/run-new.json
    .\.venv\Scripts\python.exe -B -m src.competition_ocr serve
    .\.venv\Scripts\python.exe -B -m unittest discover -s tests -v

批量输出须指定 outputs 下尚不存在的 JSON 文件。加上 --save-images 会在同级的 <结果名>-images/ 下保留原图和识别定位图；蓝桥杯通过门控时还会保存去水印图、变化掩膜和第二次定位图。服务监听 127.0.0.1:8765。默认使用本机 PaddleX 缓存中的 PP-OCRv5 mobile；如模型放在其他目录，把 --model-root '模型目录' 放在子命令前面。仅支持单张图片，不支持 PDF。

旧命令 main.py 和 evaluate_zigzag.py 保留，继续使用 samples/LanqiaoCup，见 [旧蓝桥杯流程](docs/lanqiao-zigzag.md)。依赖版本见 requirements.txt。样本和输出含个人信息，仅在本地使用，已排除在默认 Git 提交之外。

[接口、类别与样本目录](docs/competition-ocr-api.md)
