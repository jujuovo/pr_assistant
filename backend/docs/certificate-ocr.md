# 主项目证书识别辅助

本实现的运行代码、ZigZag、测试样本、PP-OCRv5模型及Python环境均位于 `pr_assistant`。不调用实验程序，不修改 Python 路径以导入实验代码，也不调用实验目录的进程。

## 已接入的操作

学生在加分申请中选择“蓝桥杯（已适配样本模板）”或“其他项目 / 完全人工核验”。学生继续自主选择适用加分规则、类别与系数；蓝桥杯可额外申报奖项、赛区、组别、赛道。提交申请后后台任务识别，学生、同院教师和管理员在原有申请详情中读取识别结果。前端自动更新排队状态，支持重跑；编辑材料会清除旧结果并排队新版本。

其他项目不加载模型、不进入识别队列、不计算自动判断置信度。蓝桥杯仅提供辅助，不自动批准申请、不修改自评或最终分数，不宣称证书真实，不推断省级/国家级认定。官方核验通道和证书库管理仍需后续调研接入。

## 本机启动

当前主项目 `.venv` 已有真实 OCR 依赖，`backend/ocr-models` 已包含两个官方移动模型，合计约22MB。前端依赖已安装。

在主项目根目录 PowerShell 运行：

```powershell
.\start-local.ps1
```

脚本复制项目附带的旧 SQLite 为 `backend/instance/certificate-local.db`，补齐已知旧字段和新增表，原数据库文件保持原样。后端和识别进程使用同一数据库，同时启动前端；登录使用附带库中原有账号。终端退出时结束本次启动的两个后端进程。数据库准备可单独执行 `./start-local.ps1 -PrepareOnly`。

默认 `config.py` 保留原 PostgreSQL 设置。本机的 PostgreSQL 在本次检查时未运行，因此本地启动脚本明确选用上述 SQLite 数据库，避免仅启动页面而识别任务无法落库。

新机器需要在主项目准备自己的环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-ocr.txt
.\.venv\Scripts\python.exe -B backend/tools/setup_certificate_models.py
cd frontend
npm ci
cd ..
.\start-local.ps1
```

首次准备模型需要访问官方模型源；已准备的本地模型运行时不需要实验目录或模型下载。`.venv`、模型、原件、生成图及本地数据库不提交 Git。换机器不能只复制源码而跳过依赖和模型准备。

## 已有 PostgreSQL 部署

先备份现有数据库；设置 Web 和 worker 相同的 `DATABASE_URL`，在 `backend` 执行 `../.venv/Scripts/python.exe -m flask --app app db upgrade`，新迁移 `20261013_certificate` 接在 `20261012_auto` 后。Web 运行 `app.py`，后台运行 `recognition_worker.py`；后者同时消费志愿材料队列和证书队列。CPU OCR 不在 HTTP 请求内执行。

未进行生产环境部署。新增迁移在隔离数据库验证，本机无法对未运行的 PostgreSQL 执行升级。

## 处理步骤与证据

1. 主项目保存上传附件，并为自动辅助任务复制不可变原件，记录SHA-256。
2. 图片处理 EXIF 方向；PDF 使用 PDFium 渲染，每份最多4页。限制10MB/文件、2000万像素/页；不支持格式或损坏文件转人工。低分辨率/明显模糊提示重新上传。清晰度阈值属于实验性规则，仍需扩充样本验证。
3. PP-OCRv5 mobile 从保留原图提取文字、坐标和 OCR 分数。
4. 仅在足够的倾斜浅色水印片段中至少两次准确识别“蓝桥杯”时，执行 ZigZag。缺失、不符、不确定及处理错误停止第二次 OCR，交教师核验。此门控只适用于已适配模板；其他年份或版式可能被转人工。
5. 固定 ZigZag CPU color，size=30、weight=90。保留处理图和全部像素变化掩码；掩码不是水印分割。算法会改变全图背景、边框及部分深色/彩色像素，原图才是审核证据。
6. 第二次 OCR 提取学校、姓名、教师、届次、赛道、组别、赛区、奖项、编号、日期。处理前后冲突、缺失/非法字段和申报不符均明确列为待人工核对。OCR 分数不能当作真实性概率。
7. 数据库任务通过原子领取、租约、版本和令牌控制并发。每页独立异常回退；修改/重跑后旧任务不能覆盖新结果。教师仍通过现有审核入口核定分数。

新增结果和原件快照通过带权限检查的 `/api/certificates/.../artifacts/...` 获取，只允许本人或同院教师/管理员。旧系统的上传文件服务及全量申请列表原有权限设计不属于此次全面重构范围。

## 代码与依赖

- `services/certificates/`：从实验迁移的核心算法，以及主项目的文件处理、队列和结果服务。
- `third_party/zigzag/`：未修改的上游代码，commit `cec0d646034b6095f5a091b804144b58cc95d1cf`，包含 AGPL-3.0 LICENSE 和来源清单。
- `services/recognition/provider.py`：主项目发布版 PaddleOCR 3.7.0，固定本地 PP-OCRv5 mobile 模型；禁用 CPU oneDNN，证书参数 max/960/box_thresh=0.4。既有志愿材料继续使用其原先的推理选项。
- `certificate_models.py`、`blueprints/certificate_bp.py`：持久化模型、权限回读、版本化重跑及证据下载。
- 前端 `CertificateSelection.vue`、`CertificateReport.vue`：项目选择、申报、状态、字段对照、原图/处理图和异常提示，接入原有申请页与公共详情弹窗。

## 验证

普通回归：在 `backend` 运行 `../.venv/Scripts/python.exe -B -m pytest tests -q -p no:cacheprovider`。

真实证书模型：设置 `RUN_REAL_OCR=1`、`PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` 后运行 `tests/test_certificates.py::test_real_standalone_certificates_and_pdf`。该测试仅使用本项目样本、环境、模型，覆盖实际上传→数据库任务→原图/处理图OCR→权限回读；两张图片的20个字段全部匹配标注，生成的扫描PDF也通过水印门控和编号核对。真实结果写入 `tests/artifacts/real_certificate_preview.json`。

已验证前端生产构建、人工通道不运行OCR、缺失水印跳过第二次OCR、坏图/坏PDF回退、低质量重传、原件哈希、跨学院禁止访问、学生不能修改审核结果、过期租约恢复、重跑版本及旧worker隔离。不能由两个样本推断其他年份、模板和扫描质量的准确率。
