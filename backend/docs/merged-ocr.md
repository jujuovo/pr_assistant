# 分类 OCR 合并说明

实验程序已迁入 backend/services/competition_ocr，运行时不导入 LAB、实验项目 src，也不引用实验虚拟环境。模型统一复用 services/recognition/provider.py 的 PP-OCRv5 mobile；水印检查、ZigZag 和字段比较复用既有 services/certificates。第三方许可证保留在 backend/third_party/zigzag。

## 已接入能力

| key | 材料 | 后端本地样本子目录 |
| --- | --- | --- |
| lanqiao | 蓝桥杯，水印通过后两次 OCR | LanqiaoCup |
| computer-design | 计算机设计大赛 | ComputerDesign |
| software-design | 软件设计大赛 | SoftwareDesign |
| challenge-cup | 挑战杯创业计划竞赛 | ChallengeCup |
| csp | CSP认证成绩单 | CSP |
| social-practice | 社会实践证明、平台截图、名单 | SocialPractice |
| other | 任职证明、成果检索报告 | Other |

16张本地样本位于 backend/samples，index.json 保存来源及SHA-256。样本、outputs及私有任务材料均已加入Git忽略。机器输出的是建议字段，官方性、真实性、是否参与和加分仍需人工核验。

## API

这些接口使用主项目登录会话，无独立HTTP服务和独立登录。

- GET /api/ocr/categories：返回7类材料。
- POST /api/ocr/{key}/recognize：multipart 的 file 字段上传一张图片，或直接发送 image/jpeg、image/png、image/webp、image/bmp、image/tiff 请求体。校验成功返回202，包含id、status、result_url；Web进程只校验和入队，不加载模型。
- GET /api/ocr/jobs/{id}：轮询到extracted、manual_review或failed；report包含fields、warnings、missing_fields、ocr_passes，artifact_urls包含受保护图片地址。
- GET /api/ocr/jobs/{id}/images/{name}：读取原图、OCR定位图；蓝桥杯额外提供处理图、第二次定位图和变化掩膜。仅本人或同院教师/管理员可访问；其他学生和外院人员无权访问。

图片最大10MB、2400万像素、短边至少120像素，仅支持单帧图片；该通用接口不支持PDF。原蓝桥杯申请接口继续支持其既有PDF处理及学生预览确认流程。

分类任务保存到ocr_job，识别完成后提供mapping字段建议，经学生确认关联MaterialRecord。正式竞赛统一接入远端规则包与教师审核计分，不新建旧Application；目录外及主动选择的人工材料不计分。旧蓝桥杯仅保留历史兼容，志愿工时流程保留。见[字段关联](ocr-material-fields.md)和[整合说明](../../docs/ocr-main-integration.md)。识别和确认不直接提交或批准材料。

## 数据库与启动

迁移顺序为20261013_materials → 20261118_ocr_jobs → 20261118_ocr_links；最后一步创建OCR任务与材料记录的唯一关联和确认快照。SQLite及现有PostgreSQL部署先执行既有迁移流程，生产库升级前按部署流程备份：

    cd backend
    ../.venv/Scripts/python.exe -B -m flask --app app db upgrade

本地使用项目原有 start-local.ps1，会通过prepare_local创建缺失表；不需要另启实验服务。Web与 recognition_worker.py 必须连接同一个数据库和私有目录。worker每轮处理原蓝桥杯、志愿时数及一份分类OCR任务；模型实例共用。租约、令牌和最大尝试次数阻止超时旧任务覆盖新结果。

默认私有文件保存在 backend/private-ocr，由OCR_STORAGE_FOLDER配置。原件上传时、识别前后及下载时均检查摘要；任务结果中不返回绝对文件路径。识别错误使用公共提示，内部异常写入后端日志。

## 独立批量验证

项目根目录 PowerShell（输出文件须不存在）：

    cd backend
    ../.venv/Scripts/python.exe -B -m services.competition_ocr categories
    ../.venv/Scripts/python.exe -B -m services.competition_ocr samples all --save-images --output outputs/merged-ocr-20261118.json

这一命令使用backend/samples、backend/outputs和backend/ocr-models，可在实验项目不参与运行时执行。首次准备模型使用项目既有tools/setup_certificate_models.py。

回归测试：

    .\\.venv\\Scripts\\python.exe -B -m pytest backend/tests -q -p no:cacheprovider

设置RUN_REAL_OCR=1、OCR_MODEL_ROOT指向backend/ocr-models可启用真实模型测试。新测试包含登录权限、同院学生隔离、队列/图片回读、摘要篡改、租约隔离及迁移的升级/回退。
