# 竞赛与证明材料 OCR 接口

| 类别 key | 样本目录（相对 samples/） | 样本数 | 提取重点 |
| --- | --- | ---: | --- |
| lanqiao | LanqiaoCup/ | 2 | 姓名、学校、届次、组别、赛区、奖项、编号、日期等 |
| computer-design | ComputerDesign/ | 1 | 届次、参赛学生、作品、指导教师、奖项、编号 |
| software-design | SoftwareDesign/ | 1 | 届次、参赛学生、获奖项目、组别、奖项、编号 |
| challenge-cup | ChallengeCup/ | 1 | 届次、参赛成员、作品、指导老师、奖项 |
| csp | CSP/ | 1 | 认证编号、姓名、日期、批次、语言、认证点、题分和总分 |
| social-practice | SocialPractice/0/、SocialPractice/1/ | 8 | 平台截图、队伍名单、实践证明分别提取 |
| other | Other/Appointment/、Other/ResearchReport/ | 2 | 任职证明提取组织、职务和任期；成果检索报告提取编号、数据库、年份 |

社会实践 0、1 按源目录保留，仅表示来源分组。CSP 是认证材料；社会实践及其他证明不作为竞赛奖项识别。程序不根据所选赛事名称推断奖项等级。

## Python

    from src.competition_ocr.service import CompetitionOCR
    ocr = CompetitionOCR()
    result = ocr.recognize("samples/LanqiaoCup/example4.jpg", "lanqiao")

同一个实例复用模型；也可调用 recognize_bytes(payload, key)。每次调用处理一张图片，输入原件不会修改。默认不返回原始 OCR 全文，也不保存处理图。Python 路径接口可传 image_dir 指定尚不存在的图片目录；命令行批处理使用 --save-images。蓝桥杯水印门控通过后才进行第二次 OCR；其他类别一次 OCR。需要旧版完整文字结果、对照评估和原有输出格式时使用 main.py。

## HTTP

    .\.venv\Scripts\python.exe -B -m src.competition_ocr serve
    curl.exe http://127.0.0.1:8765/api/ocr/categories
    curl.exe -X POST http://127.0.0.1:8765/api/ocr/lanqiao/recognize -H "Content-Type: image/jpeg" --data-binary "@samples/LanqiaoCup/example4.jpg"

POST /api/ocr/{category}/recognize 接收原始图片字节，不是 multipart 表单。支持 JPEG、PNG、WebP、BMP、TIFF 单帧图片，最大 10 MB、2400 万像素。服务是本机、串行的实验接口。

正常响应包含 category、material_kind、status、fields、missing_fields、warnings、ocr_passes、source_sha256。extracted 表示已完成字段提取；manual_review 表示缺失、冲突或需要平台核对，两种状态均返回 HTTP 200。无效图片返回 400，未知路由或类别 404，超限请求 413，不支持的请求类型 415，模型异常 500。

authenticity 始终为 not_assessed，requires_human_verification 始终为 true。提取字段应人工对照原件，社会实践截图还须对照学校平台。样本数量有限，现有适配结果不代表其他年份和版式都可识别。
