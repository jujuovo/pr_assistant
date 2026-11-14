# CertificateOCRLAB

蓝桥杯证书识别实验：原图 OCR → 蓝桥杯水印检查 → ZigZag 辅助图 → 再次 OCR → 字段提取与对照 → 异常人工复核。保留原始材料，不认定真实性，不计算加分。

## 直接运行

在项目根目录的 PowerShell 中运行：

    & '.\.venv\Scripts\python.exe' -B main.py
    & '.\.venv\Scripts\python.exe' -B evaluate_zigzag.py

默认使用 samples/LanqiaoCup 的两张图片、PP-OCRv5 mobile、CPU 4 线程、关闭 MKLDNN，检测长边 960、检测框阈值 0.4；默认开启蓝桥杯水印检查和 ZigZag color / CPU。每次新建 outputs/run_<时间> 目录；评估器默认选择最近的已完成 ZigZag 结果，跳过仍在运行的任务及损坏的汇总。

本实验的默认设置仅对应已确认应有“蓝桥杯”水印的模板。其它材料须关闭预处理或另行配置模板，不能直接按蓝桥杯水印规则判断其可靠性：

    & '.\.venv\Scripts\python.exe' -B main.py --input '图片路径' --no-preprocess-watermark

可指定输入文件、图片目录和新的空结果目录：

    & '.\.venv\Scripts\python.exe' -B main.py --input samples/LanqiaoCup --output outputs/my_run
    & '.\.venv\Scripts\python.exe' -B evaluate_zigzag.py --output outputs/my_run

输出目录已有内容时拒绝覆盖；通过独占创建 run.json 在模型加载前预留目录，阻止两个任务同时使用同一输出位置。输出不能位于输入图片目录内。同名不同扩展名图片分别保存结果。单张图片或 OCR 失败不会丢掉其它图片的记录；summary.json 每处理完一张即保存，存在处理失败时程序返回非零退出码。模型初始化失败记录 startup_failed；运行状态保存在 run.json。汇总及检查 JSON 使用完整临时文件原子替换，避免半写入记录。

## 核心目录

- main.py：正式命令行入口与批处理。
- src/zigzag_preprocess.py：水印门禁、ZigZag 调用和处理记录。
- src/watermark_preprocess.py、watermark_filter.py：水印检查与可选局部清除。
- src/ocr_comparison.py：10 项字段提取，冲突、缺失及格式异常检查。
- third_party/zigzag/zigzag.py：未修改的上游实现；LICENSE、UPSTREAM.json 保存许可和来源。
- evaluate_zigzag.py：结果核对工具，不运行模型。
- tests/fixtures：人工参考字段和此前 ZigZag 处理图的独立像素哈希。
- samples：原始样本；outputs：正式结果；.venv：现有运行环境。
- archive：归档的历史三方法对照代码和资料，不是核心运行依赖。

核心程序不依赖历史实验目录。原图、历史输出及归档放在本地，仓库仅保存实验代码和测试。

## 门禁及复核

蓝桥杯水印需满足浅色、倾斜和重复条件：至少 3 个候选，其中至少 2 处文字精确匹配、OCR 分数不低于 0.8。缺失、不匹配、不确定或无效 OCR 坐标/分数均停止去水印后 OCR。水印身份不是证书真实性结论。

ZigZag 失败或将所有原有深色像素抹去时停止自动处理，保存原因。两次 OCR 字段冲突、处理后任一预期字段缺失、截断组别或无效日期均要求复核，避免“两次都漏识别”被当作通过。学校或姓名为空时不会取下一项字段标签来补值；连续标签也不会混入姓名。缺少教师姓名等字段也会提示复核，是否必需可在后续业务规则中配置。

## 参数

- --no-preprocess-watermark：普通图片 OCR，关闭蓝桥杯图像预处理；普通 OCR 字段缺失仍提示复核。
- --watermark-method zigzag：默认；--watermark-method mask 保留旧局部清除。
- --expected-watermark 蓝桥杯：预期水印文字，不能为空。
- --zigzag-size 30、--zigzag-weight 90、--zigzag-threshold-offset 0：ZigZag 参数。
- --gray-min 180、--gray-max 245：仅用于 mask 方法。
- --no-watermark-filter：关闭 OCR 文字过滤，不关闭图像预处理。
- --model mobile/server、--cpu-threads 4：模型与 CPU 设置。

ZigZag 对整张图归一化，会改变边框、深色笔画和颜色。pixel_change_mask.png 表示所有变化像素，不是水印分割掩膜；processed.png 仅供 OCR。旧 mask 方法的 watermark_mask.png 含义不同。

## 输出与检查

每张图片保留原始副本及 SHA256、raw/processed OCR、watermark_check.json、processed.png、像素变化图、ocr_comparison.json、result.json 和文字输出。原图与处理图均从同一份证据副本读取。处理失败记录阶段、原因及人工复核标记；不静默回退到另一算法。

    & '.\.venv\Scripts\python.exe' -B -m unittest discover -s tests -v

有本地人工标注时评估器计算字段正确数；没有标注时显示“无人工标注”。评估记录的子目录和图像路径必须位于指定结果目录内。校验使用显式错误检查，Python 优化模式不会跳过证据哈希或像素检查。参考答案可通过 --expected 指定。

当前不支持 PDF、自动图像质量判断、证书库或官方核验接口。原始样本识别结果不能推广为生产准确率。

## 环境与归档

按 README 创建 .venv 并安装 requirements.txt 中的发布版依赖。模型保存在本机 PaddleX 缓存中。

默认不生成缓存的执行方式是上述 -B 命令。缓存文件清理不会删除 .venv 的已安装库、OCR 模型或原始样本。archive 中历史文件里的旧路径描述的是当时的实验布局。
