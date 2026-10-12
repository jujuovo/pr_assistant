# 志愿工时自动化后端接入

后端已实现批量上传、数据库任务队列、信用/荣誉独立提取、表格预览、跨批次去重、人工核定与年度共用上限计分。前端未修改，现有页面不会自动出现新上传按钮或预览表格；前端后续按以下接口渲染 rows。

## 启动

在 pr_assistant 根目录运行；已有测试环境 `.venv` 中安装了 Flask、数据库驱动及 OCR。

```powershell
# 使用团队指定的数据库；不要把测试 SQLite 配置带入正式环境。
# 可选：$env:DATABASE_URL = 'postgresql://用户名:密码@主机:5432/数据库'
cd backend
..\.venv\Scripts\python.exe -m flask --app app db upgrade
..\.venv\Scripts\python.exe app.py
```

另开一个终端，在 backend 中启动识别 worker：

```powershell
..\.venv\Scripts\python.exe recognition_worker.py
# 只消费一个批次，可用于调试
..\.venv\Scripts\python.exe recognition_worker.py --once
```

Web 和 worker 必须使用同一 DATABASE_URL、同一个 private-materials 目录。代码没有在请求内启动线程或 shell 子进程。单 worker 复用模型，租约超时可恢复；多个 worker 用数据库条件更新竞争领取，旧令牌不能写回结果。默认租约 10 分钟，需根据实际 CPU 大批量推理时间调整。

新机器可在独立 Web 环境安装 `requirements.txt`，在独立 OCR worker 环境安装 `requirements-ocr.txt`。两个环境都在本项目内创建，不依赖 LAB。OCR 使用已验证的 PaddleOCR 3.7.0 / PaddlePaddle 3.3.1，CPU mobile 模型，关闭 MKLDNN。首次无缓存时需下载模型。

迁移文件为 `20261012_auto_materials.py`，接在现有 head `6be17e8f4f8a` 后面，只新增五张表与索引，不修改历史申请字段。本次仅在隔离数据库测试迁移，未执行团队数据库迁移，也未设置真实政策。

## 1. 配置政策（学院管理员）

使用既有登录 session cookie，所有新增接口都验证账号和学院权限。学生只能操作自己材料；老师和管理员只能查看/审核本学院。

`PUT /api/automation/volunteer/policies/2026`

```json
{
  "credit_rate": "0.01",
  "honor_rate": "0.01",
  "max_score": "2",
  "honor_enabled": false,
  "start_date": "2025-09-01",
  "end_date": "2026-08-31"
}
```

以上数字只是接口示例，不是实际推免政策。计算方式：核定小时 × 对应类型每小时分值，信用与荣誉共用学生年度上限。当前支持比例计分，不执行任意公式或 AI 生成分数。预览与正式计分统一使用四位小数 HALF_UP：先对封顶后的累计分舍入，再以相邻累计分之差分配批次增量，不对各批次原始增量独立舍入，避免合计突破年度上限。

信用时数单活动申请及审核核定均最多15小时（包含15，不是整批合计上限）。显式填写 claimed_hours 超过15会返回400；未填写时默认申请 min(截图时数, 15)。超过15的原始截图时数不会被改写，预览会提示截限，分数按申请值估算；教师不能用审核意见绕过15小时核定上限。荣誉时数不使用此单活动限制，仍遵守学院政策及年度上限。

`GET /api/automation/volunteer/policies/2026` 查询政策。未配置时，预览分数返回 null、不能提交，不擅自用默认比例。年度已有申请提交后政策冻结，避免已认定和未认定批次使用不同上限；若需中途调整政策，须另设计显式版本迁移/重算，不能用本接口悄悄覆盖。

## 2. 按类型批量上传（学生）

`POST /api/automation/volunteer/batches`，multipart/form-data：

| 字段 | 内容 |
| --- | --- |
| material_type | 每批只能选择 `credit` 或 `honor`，也支持完整名 `volunteer_credit/volunteer_honor` |
| year | 对应政策年度，比如 2026，不必等于活动自然年 |
| files | 重复同名字段上传多张图片 |
| claimed_hours | 可选 JSON 数组，如 `[5.05, 2, null]`，顺序和 files 一致 |

返回 HTTP 202，包含 id、status、version、rows。单张最大10MB、最多30张、请求总大小遵守现有 Flask 100MB限制；只接受实际验证过的单页 JPG/PNG/WEBP/BMP，最大20MP。文件使用随机名存入 backend/private-materials，不走已有公开 uploads 路径。

上传时选定类型，worker 再验证截图标题；混入另一类页面的行变成 wrong_type，不能自动提交。全批一个 material_type，不支持一个上传请求同时传 credit 和 honor。

如果整批选错类型，使用 `POST /api/automation/volunteer/batches/{id}/reclassify`，提交 `{"version": 2, "material_type": "honor"}`。只允许学生纠正未提交且识别完成的批次；保留原项和去重历史，重新识别，记录类型修正审计。已有重复行不会因此变成可通过；混合两种页面仍需分开批次，不能把错误行强行通过。

## 3. 轮询并渲染字段预览

`GET /api/automation/volunteer/batches/{id}`

批次状态：queued → processing → completed → submitted → approved/rejected；failed 可重试。

每行 rows 包含：id、filename、status、displayed_hours、claimed_hours、requested_hours、confirmed_hours、credit_max_hours、activity_name、activity_dates、check_in/check_out、recorded_at、fields、estimated_score_before_cap、duplicate_of、can_submit、warnings、cross_type_conflicts、error、image_url。requested_hours 是本次申请时长；信用优先使用合法申报值，未申报时对识别值截限15，credit_max_hours 为字符串 "15"；荣誉该上限字段为 null。

异常时数（非有限、超过通用数值范围或超过四位小数）逐项标记 incomplete，保留原文、错误和证据，该行不能提交，不会使正常行的预览返回错误。

- 信用：时数、活动名、签到签退；activity_dates 来自签到签退。
- 荣誉：时数、志愿者、录入人、组织、录入时间、类型、原因；activity_dates 仅从原因中的明确日期提取，录入时间绝不替代活动时间。名称性原因没有日期时，返回空数组，教师通过审核时必须补充实际日期及依据。
- 原文、识别分数和坐标保留在 fields[*].evidence。组织名等 OCR 漏字不自动补写。
- estimated_score_before_cap 为每行上限前预计分，行分数舍入后相加不作为批次计分依据。未批准批次的 estimated_incremental_score 为本批扣除既有年度上限占用后的条件建议分；提交后只包含选中明细。日期缺失、身份不明等提示仍须人工确认。
- 已批准批次的 estimated_incremental_score 与新增字段 final_score 均返回当前实际入账分数，来自年度分配后的计分快照；撤销后两者为零。未完成审核时 final_score 为 null。撤销其他批次引发年度重算后，预览会反映最新分配结果。

`GET /api/automation/items/{id}/image` 返回受保护的本次上传原图；活动重复但图片不同的行仍展示本次图片，方便核查修改痕迹。仅相同文件去重、当前项没有单独存储图片时回退到原项的相同文件。`GET .../{id}/evidence` 返回完整 OCR 和提取结果。

`GET /api/automation/volunteer/batches?page=1` 获取20条分页记录。

`POST /api/automation/volunteer/batches/{id}/retry` 只重试未提交的 failed/incomplete 项，不允许将 duplicate 或 wrong_type 改为可通过。建议传 `{"version": 最新版本}`；兼容无请求体，但始终以请求读取的版本执行原子条件更新。重试、类型修正、提交及审核统一按学生→批次保护状态变化，旧请求返回409，不能覆盖已经提交或批准的批次。worker 不领取已关联申请的批次。

## 4. 提交申请

`POST /api/automation/volunteer/batches/{id}/submit`

```json
{"version": 2, "item_ids": [10, 11]}
```

version 必须使用最新 GET 结果。省略 item_ids 时只选择 can_submit=true 的行；不可选重复、类型错误、缺少时数/记录标识或不在政策期间的行。荣誉未启用时不能提交。部分正常行可以单独提交，申请的 self_score 仅按选中明细及剩余年度额度计算，与提交后的批次预览一致；未选中的行不计入。重复行仍保留 duplicate 状态，不会被通过。

部分提交后，未选中的非重复材料会自动移入新的 completed 批次，响应和之后的 GET 返回 remaining_batch_id；新批次 GET 返回 source_batch_id。可继续提交正常行，重试 incomplete/failed 行或修正 wrong_type。材料ID、原图、证据和去重指纹保持不变，不需要重新上传；拆分关联和移动明细记录在审计中。已判重复的行留在原批次，不会通过拆分解禁。提交原批次的旧请求仍返回409。

后端创建现有 Application：application_type=comprehensive，动态数据包含 project_category=volunteer 和 automation_batch_id，审核前 final_score 为空。旧的成绩统计可继续汇总，不引入中文类型导致漏计。

## 5. 逐项审核与计分

`POST /api/automation/volunteer/batches/{id}/review`

也可以使用既有 `POST /api/applications/{application_id}/review`，自动化申请会路由到同一服务，但必须提交新的明细字段。旧前端若只传 finalScore 会提示必须逐项核定，不会绕过自动化明细。

```json
{
  "version": 3,
  "status": "approved",
  "reviewComment": "原图与实际记录已核对",
  "items": [
    {"id": 10, "decision": "approved", "confirmed_hours": "5.05", "activity_dates": ["2025-12-21"], "comment": ""},
    {"id": 11, "decision": "rejected", "comment": "不在认定范围"}
  ]
}
```

items 必须覆盖本批所有已提交行，不能重复 ID。核定值与截图不同、姓名不符、时数冲突、低识别分数或补充/修改荣誉日期时需写依据。信用日期不能脱离截图日期。重复项即使提交100分也不能通过；客户端 finalScore 不作为计分依据。

cross_type_conflicts 中同名同日且 blocking=true 的记录属于明确跨类型重复，不能提交或通过审核。优先保护已提交记录与先上传的原项。名称缺失、截断或自由文本不同但日期重合时，match=needs_verification：教师必须在该行传 `distinct_activity_ids: [冲突材料ID...]`，与当前全部疑似冲突一一对应，并在 comment 记录核查两份来源材料后确认是不同活动的依据。仅填写普通意见不够；明确重复不能用此字段放行。审核补充荣誉日期后会重新计算冲突，不能仅凭首次日期缺失或旧预览放行；人工确认日期的真实性仍须核对平台来源。

version 和明细ID必须是正整数，不能用布尔、小数或数组代替；material_type 必须是字符串；审核意见必须是最多2000字的字符串。字段格式错误返回400，不会返回500或留下部分审核结果。

拒绝/撤销整个批次：`{"version": 3, "status":"rejected", "reviewComment":"撤销认定"}`。撤销后年度其他批次重新分配上限内分数，更新最终综合成绩。

同一学生年度上限按所有已通过批次汇总，按 batch ID 稳定分配增量。审核、分数快照、审计和学生成绩在同一事务内提交；同一学生行锁防止并发审核重复占用上限。例：上限1分，先后通过两个0.505分批次，分配0.505及0.495，而非累计1.01。

## 去重边界

- 同一学生、跨批次/年度的相同文件 SHA256 立即标 duplicate，当前批次重复也一样。
- 信用活动：相同签到和签退记录只认一次，不依赖截断活动名。
- 荣誉补录：姓名+录入时间+类型+活动日期+规范化原因识别记录，避免批量录入同一秒的不同活动被误拒；原因中的日期提取为排序去重集合，与正文分离，日期格式、排列顺序不影响重复检查。明确活动日期与原因正文相同的后续补录也拦截，不把时数纳入重复键。历史材料重新计算事实键及活动键，不依赖旧版指纹；审核补充日期后再次检查。
- 信用与荣誉跨类型：按同一学生的活动日期和名称检查明确重复；同日而身份不足的记录进入逐项人工冲突核查。读取预览、提交及审核均检查，不能只依赖首次识别时的提示。
- 数据库唯一约束防并发重复。重复记录不删除，duplicate_of 指向原项；申请驳回不删除上传历史，需要修正时应处理原记录而非再次上传。
- 这些属于记录重复检测，不是图像验真。修改全部时间/身份的伪造截图、日期识别错误、不同不完整原因仍可能无法自动证明重复，人工排除冲突必须核对原件/平台活动详情，不能把 OCR 或文字意见当作验真。没有平台唯一活动ID时，无法承诺识别所有改写材料。
- 旧系统历史附件未自动索引；正式切换前应明确旧数据范围并回填识别/去重记录，不会擅自把历史人工成绩重新计算。

## 管理删除与材料保留

已有自动化材料、去重记录或审核审计关联的账号不能直接物理删除，管理接口返回409，建议停用账号保留证据。学院、系、专业的级联删除同样检查涉及的学生和申请；已有自动化政策的学院也不能直接删除。此处不自动清空政策、审计或重算历史分数，不改变原有管理接口的权限设计。

没有自动化关联时保留原来的删除功能。普通申请附件只在数据库成功提交后清理；外键冲突返回409，其他提交失败返回500，记录和附件保持原样。文件清理失败会保留文件并记录日志，不将已经提交的数据库删除误报为可回滚。生产数据库仍需保留外键约束以兜底并发关联写入。

## 测试

批量处理优化：状态切换使用批次+明细批量刷新，避免每张图片单独查询；跨类型冲突按日期建立当前请求内的倒排索引，历史项日期及名称只解析一次。审核在学生锁内一次构建荣誉事实/活动哈希索引，人工核定日期变化同步更新索引；不跨请求、事务或 worker 写回复用缓存，防止过期事实放行。候选查询不读取大体积 raw_ocr，批次类型预加载避免逐条查批次。年度重计分批量加载明细和关联申请，每批费率只解析一次，保留 Decimal、HALF_UP 四位小数及共用上限规则。

计数式性能回归见 tests/test_automation_performance.py：检查30项状态刷新查询上限、30项预览/120项历史的解析次数、1项与30项审核的历史查询次数一致、30个已批准批次的计分读取及年度额度分配，并对照旧扫描规则验证冲突结果。优化不改变 OCR 模型、置信度、真实性判断或审核政策；活动全挤在同一天时仍必须处理所有真实冲突，不会为速度省略检查。

```powershell
cd E:\course\InteractionDesign\pr_assistant
.\.venv\Scripts\python.exe -m pytest backend\tests -q
# 可选真实 OCR，样本已复制到本项目忽略目录，不修改 LAB
$env:RUN_REAL_OCR = '1'
.\.venv\Scripts\python.exe -m pytest backend\tests\test_real_ocr.py -q
```

后续证书接入：在 services/recognition 的注册表新增适配器，再增加该项目的审核事实和计分策略；复用批次、材料存储、证据、身份权限、任务领取和审计，不复制志愿服务公式。
