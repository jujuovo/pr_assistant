# 自动识别流程代码重构

本次整理蓝桥杯证书与志愿材料的自动识别服务、预览确认及证书结果展示。以重构前工作区为基线，包括此前新增的质量拦截和原件摘要检查；接口、数据库结构、模型参数、两次OCR顺序、字段优先级、错误提示及状态转换保持原有行为。

## 长函数与职责划分

按 Python AST 的函数起止行统计，包含函数内部空行与注释。

| 位置 | 函数 | 重构前 | 重构后 | 拆分后的职责 |
| --- | --- | ---: | ---: | --- |
| services/recognition/worker.py | run_one | 106 | 47 | 保留任务领取、事务及租约校验；分离推理、明细状态处理、去重与超时失败处理 |
| services/recognition/volunteer.py | extract | 100 | 30 | 编排时数、活动、荣誉字段提取及校验；各阶段独立实现 |
| services/certificates/pipeline.py | process_page | 47 | 23 | 编排质量检查、原图OCR、水印门控及处理图OCR；分离结果保存与差异警告 |
| services/certificates/preview.py | save_preview | 66 | 33 | 保留授权、质量与原件检查、版本更新事务；分离请求字段和申请期校验 |

识别核心的两个服务目录现有函数最长94行。相关自动化服务和专用接口也纳入下面的100行检查。

## 重复逻辑整理

- `services/recognition/serialization.py`：共用OCR/numpy结果JSON规范化，保持拒绝NaN和Infinity的行为。
- `services/recognition/worker.py`：集中当前任务令牌查询条件，保留领取、续租、超时失败和结果提交各自的事务边界。
- `services/certificates/pipeline.py`：统一两次OCR证据文件的保存方法，文件名称与JSON格式保持一致。
- `services/certificates/fields.py`：集中后端证书字段及顺序；`preview.FIELDS`继续可以被原调用方导入。
- `services/certificates/ocr_comparison.py`：证书编号只使用原先最终生效的逐行提取逻辑，删除总会被覆盖的预提取结果，保留字段输出顺序。
- `frontend/src/services/certificateFields.js`：预览与教师详情共用字段名称、顺序和识别值回退方法；优先处理图，没有值时采用原图。
- `CertificatePreview.vue`：删除只捕获并原样抛出异常的冗余分支，保留finally中恢复保存状态的行为。

## 长函数检查

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -B backend/tools/check_recognition_structure.py
```

该工具检查识别服务目录、`services/automation.py`、识别专用蓝图和worker启动入口；出现超过100行的函数时返回非零退出码。它不等同于全仓库所有业务函数均小于100行。

初始扫描也发现通用申请接口中的 `get_applications`（197行）、`get_application`（105行）、`create_application`（258行）、`update_application`（275行）、`review_application`（104行）、`get_pending_applications`（126行）。这些函数涵盖全项目申请、组织信息、计分及文件管理，可作为下一轮通用业务重构的范围。前端通用申请表单还存在`loadEditData`（192行）、`calculateTreeScore`（188行）；证书预览和教师识别详情组件中没有超过100行的函数。

## 验证与行为边界

对比重构前后的242组志愿材料输入、260组证书文本输入、JSON规范化边界和5条证书处理分支，检查字段及顺序、完整警告列表、错误类型、OCR调用次数与证据文件字节一致。对比基线保存在开发验收目录，运行程序不依赖这些文件。

运行完整后端回归（设置`RUN_REAL_OCR=1`启用真实模型）、前端接口测试和生产构建。现有回归覆盖租约恢复、旧任务隔离、重复材料、人工审核、评分、原件校验与预览提交。本轮后端199项全部通过（含3项真实OCR），前端7项全部通过，生产构建通过。长函数检查覆盖124个函数，最长94行。构建保留既有大文件提示，后端存在既有依赖和SQLAlchemy警告。

此前识别出的像素超限异常归类、日期一致性、官方核验接入等业务问题继续单独跟踪，避免把功能变化混入结构重构。ZigZag上游实现与许可证保留原样。
