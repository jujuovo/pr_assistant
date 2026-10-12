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

## 6. 前端与后端对齐实施指南

本节是前端开发的现行接口契约，而不是已完成的前端实现。此次只补充文档；前端页面、请求模块、路由及交互仍需前端同学实现。遇到本节明确标注的接口缺口，应先确定新增接口方案，不能通过修改前端字段或调用旧人工申请接口绕过后端规则。

### 6.1 接入位置、请求前缀与身份

项目有两套前端目录，先由团队确定实际维护哪一套，不要在两个入口重复接线：

| 现有前端 | 现有请求封装 | 建议新增模块（尚未创建） |
| --- | --- | --- |
| 原版 | `frontend/utils/api.js` | `frontend/utils/volunteerApi.js` |
| 10.12调整版 | `frontend_10.12修改/src/services/api.js` | `frontend_10.12修改/src/services/volunteerApi.js` |

两套现有封装的 `API_BASE_URL` 都是 `/api`。若复用 `api.apiRequest`，传 `/automation/volunteer/batches`，不要再传 `/api/automation/volunteer/batches`，否则会拼出重复的 `/api/api/...`。新增独立请求模块也可以直接请求完整的相对路径 `/api/automation/...`，但必须与旧模块共享同一个后端地址和登录 session。

开发时两套 `vite.config.js` 的 `/api` 代理目前指向 `http://localhost:5001`，应与实际 Flask 端口一致；生产环境将 `/api` 交由同域反向代理。推荐同域访问，不要求前端直接使用后端绝对地址。私有截图也在 `/api/automation/...` 下，不需要公开映射 `private-materials`。

新接口认证依赖后端 session cookie，JSON 请求、文件上传和原图请求均必须带上该会话。现有 `credentials: 'include'` 可以复用；单独添加 `Authorization: Bearer ...` 或在请求体中提交 `studentId/facultyId/currentUserId` 不能代替会话。学生和学院身份由服务端确定，不能让用户在上传表单里指定另一个学生。页面恢复时先检查后端 session，不能只依据 localStorage 的登录标记判断已登录。若必须跨域部署，需要额外核对允许的前端来源、cookie 属性及代理配置，不能仅靠 `credentials` 保证认证成功。

### 6.2 页面、动作与接口对应表

下表使用完整请求路径。`{batch_id}` 是自动化批次ID，`{item_id}` 是识别明细ID，`application_id` 是旧申请ID，三者不能混用。

| 页面/动作 | 方法与路径 | 请求内容 | 成功响应/角色 |
| --- | --- | --- | --- |
| 学生/审核页读取本学院年度政策 | `GET /api/automation/volunteer/policies/{year}` | 无 | 200，`{policy, revision}`；有学院关联的已登录账号 |
| 管理员保存年度政策 | `PUT /api/automation/volunteer/policies/{year}` | 第1节政策对象 | 200，`{policy, revision}`；本学院管理员 |
| 学生上传一批材料 | `POST /api/automation/volunteer/batches` | FormData，见第2节 | 202，完整批次预览；学生 |
| 我的批次/学院批次列表 | `GET /api/automation/volunteer/batches?page=1` | 仅分页参数 | 200，`{page, batches}`；学生限本人，教师/管理员限本学院 |
| 查看批次/轮询识别结果 | `GET /api/automation/volunteer/batches/{batch_id}` | 无 | 200，完整批次预览；按本人/学院权限 |
| 查看原图 | `GET /api/automation/items/{item_id}/image` | 无，携带 cookie | 200，图片二进制；按所属批次权限 |
| 展开识别证据 | `GET /api/automation/items/{item_id}/evidence` | 无 | 200，`{report, ocr}`；按所属批次权限 |
| 重试失败/不完整明细 | `POST /api/automation/volunteer/batches/{batch_id}/retry` | `{version}` | 202，完整批次预览；所属学生或本学院教师/管理员 |
| 修正整批材料类型 | `POST /api/automation/volunteer/batches/{batch_id}/reclassify` | `{version, material_type: 'credit'或'honor'}` | 202，完整批次预览；学生 |
| 提交所选识别明细 | `POST /api/automation/volunteer/batches/{batch_id}/submit` | `{version, item_ids}` | 201，完整批次预览，内含 `application_id`；学生 |
| 通过/逐项拒绝/整批驳回/撤销 | `POST /api/automation/volunteer/batches/{batch_id}/review` | 第5节审核对象 | 200，完整批次预览；本学院教师/管理员 |

202只代表请求被接受，不代表OCR已完成；201代表已创建待审核申请，不代表已加分。封装应接受所有 `response.ok` 的2xx状态，不能只认200。上传若全是相同文件重复，202响应中的批次也可能已经是 `completed`，应根据实际状态决定是否轮询。

批次列表每页固定最多20条，只返回概要，没有 `rows`、`policy`、`total`、`pages`、`has_next` 或学生姓名/学号。需要详情时再请求单批次；下一页返回空数组时结束，最后一页少于20条也可结束。当前不支持服务端按 `year/status/material_type/student_id` 过滤列表，不能假定带这些参数就能筛选；前端仅筛选当前页也不能冒充完整搜索结果。管理员的已提交申请列表建议复用旧申请列表及其学生信息，再按批次ID打开专用审核页。

政策GET返回没有 `frozen` 字段，不能根据revision推断是否可修改。页面可提供保存操作，但PUT返回政策冻结的409时须提示不可修改并保留原政策；如需要进入页面就准确显示冻结状态，应补充正式只读字段契约。

### 6.3 请求封装必须补齐的能力

旧 `apiRequest` 在错误时只读取 `responseData.message`，但自动化接口的常见错误是 `{"error":"原因"}`，因此直接复用会把具体原因变成“请求失败”；抛出的普通 Error 也没有HTTP状态，页面难以区分401和409。前端接入时应统一兼容 `error` 与 `message`，并保留 `status`、响应数据以及用户取消/请求超时的区别。下面是可以采用的独立模块示例，**只作为文档示例，没有写入前端文件**：

```javascript
// volunteerApi.js 示例；同域代理，不能再经过旧 API_BASE_URL 拼接。
async function requestAutomation(path, { method = 'GET', data, signal, timeoutMs = 30000 } = {}) {
  const controller = new AbortController()
  let timedOut = false
  const cancel = () => controller.abort()
  if (signal?.aborted) cancel()
  signal?.addEventListener('abort', cancel, { once: true })
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  const multipart = data instanceof FormData
  try {
    const response = await fetch(`/api/automation${path}`, {
      method,
      credentials: 'include',
      cache: 'no-store',
      signal: controller.signal,
      headers: data !== undefined && !multipart ? { 'Content-Type': 'application/json' } : {},
      body: data === undefined ? undefined : multipart ? data : JSON.stringify(data)
    })
    // 代理的413/502等可能返回HTML，不能不加判断直接 response.json()。
    const contentType = response.headers.get('content-type') || ''
    const payload = contentType.includes('application/json') ? await response.json() : null
    if (!response.ok || payload === null) {
      const error = new Error(payload?.error || payload?.message || `接口异常（HTTP ${response.status}）`)
      error.status = response.status
      error.payload = payload
      throw error
    }
    return payload
  } catch (error) {
    if (timedOut) {
      const timeout = new Error('请求超时；操作可能已到达服务器，请先查询状态，勿自动重复提交')
      timeout.code = 'REQUEST_TIMEOUT'
      throw timeout
    }
    throw error
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', cancel)
  }
}

export const volunteerApi = {
  getPolicy: year => requestAutomation(`/volunteer/policies/${year}`),
  savePolicy: (year, policy) => requestAutomation(`/volunteer/policies/${year}`, { method: 'PUT', data: policy }),
  listBatches: (page = 1) => requestAutomation(`/volunteer/batches?page=${page}`),
  getBatch: (id, signal) => requestAutomation(`/volunteer/batches/${id}`, { signal }),
  getEvidence: id => requestAutomation(`/items/${id}/evidence`),
  upload: form => requestAutomation('/volunteer/batches', { method: 'POST', data: form, timeoutMs: 60000 }),
  retry: (id, version) => requestAutomation(`/volunteer/batches/${id}/retry`, { method: 'POST', data: { version } }),
  reclassify: (id, version, material_type) => requestAutomation(`/volunteer/batches/${id}/reclassify`, {
    method: 'POST', data: { version, material_type }
  }),
  submit: (id, version, item_ids) => requestAutomation(`/volunteer/batches/${id}/submit`, {
    method: 'POST', data: { version, item_ids }
  }),
  review: (id, data) => requestAutomation(`/volunteer/batches/${id}/review`, { method: 'POST', data })
}
```

图片接口不是JSON，不得通过上述 `requestAutomation` 或旧JSON封装读取。30/60秒是前端示例超时，不是后端OCR运行时限；请求超时只能取消前端等待，不能证明服务器没有上传/提交/审核成功，也不应触发自动重发POST。超时或断网后先读取已知批次状态；若上传响应丢失导致没有批次ID，可刷新批次列表让学生确认，当前没有幂等请求ID或“找回指定上传请求”的接口。

### 6.4 上传表单与申报时长

学生上传页至少需要：政策年度、信用/荣誉单选、图片列表、可选的信用申报时长、上传按钮。切换类型或年度前提示是否清空未上传材料，不能把信用和荣誉图片拼到同一请求中。政策读取返回 `policy: null` 时提示联系管理员；后端允许先上传识别但不允许提交。`honor_enabled: false` 时前端可以禁用荣誉申请入口，并说明此年度不计荣誉。

以下示例中的 `entries` 是前端自行维护的列表，每项包含 `file: File` 和 `claimedHours: string|null`，不是后端返回对象：

```javascript
const form = new FormData()
form.append('material_type', selectedType) // 'credit' 或 'honor'，仅 append 一次
form.append('year', String(selectedYear))
entries.forEach(entry => form.append('files', entry.file, entry.file.name))
if (selectedType === 'credit') {
  form.append('claimed_hours', JSON.stringify(entries.map(entry => {
    const input = entry.claimedHours == null ? '' : String(entry.claimedHours).trim()
    return input === '' ? null : input // 保留小数字符串，避免先转换为浮点数
  })))
}
const batch = await volunteerApi.upload(form)
// batch 是直接返回的预览对象，不是 {data: batch} 或 {batch: batch}。
```

- `files` 必须重复使用同名字段，不能改成 `files[]`，也不能把 File 数组转成JSON。`claimed_hours` 必须是JSON字符串，长度和图片数量一致；增删/排序图片时同步调整申报值。空值传null，不传空字符串、布尔值或非数字文本。
- 信用申报时长前端先校验非负、最多四位小数、每活动不超过15，再提交后端；后端仍作最终校验。没有申报值时采用 `min(识别时数, 15)`。批次内合计超过15不因此禁止上传。
- 荣誉暂不展示独立申报时长输入，默认不传 `claimed_hours`：后端虽能存该字段，但荣誉的 `requested_hours` 和预览计分使用截图显示时数，不按独立荣誉申报值估算，最终由教师核定。若产品要求“荣誉申报时长与截图分别填写并按申报计分”，需另行扩展契约。
- 上传前检查1至30张、每张不超过10MB、整体不超过100MB、允许的单页图片格式；后端会再验证真实格式、像素和图片完整性，不能仅依赖文件扩展名。不要自己设置 multipart 的 Content-Type，否则可能缺少 boundary。
- 当前没有 `PATCH item`、上传后修改 `claimed_hours` 或按文件删除识别项的接口。学生预览表中的申请时长应只读，不能显示“保存修改”却无接口；识别前选择默认值或上传前填写。如需识别后调整申报值，先增加正式接口，不能重复上传或改旧申请数据绕过去重。
- 上传按钮有独立 `uploading` 状态防重复点击。上传结束以后保留服务端批次ID、响应状态和版本；不要把本地文件名或数组序号当成明细ID。

### 6.5 异步识别、状态与轮询

上传后立即渲染返回的占位/重复行，仅在 `queued/processing` 时轮询。建议每2至3秒读取一次详情；采用等待上次请求结束后再安排下一次的方式，不要用无保护的 setInterval 产生重叠请求。页面离开、切换批次或退出登录时清除定时器并中止当前GET。连续网络错误应退避并显示“重新连接”，不要把失败轮询当作OCR失败，也不要让旧批次响应覆盖当前打开的批次。

每次收到详情都以服务端数据替换当前批次快照和 `version`。当前批次没有进度百分比或完成时间估计字段，可展示“已处理项数/总项数”，但不能据此承诺准确耗时。worker处理中的行会逐步更新；**只有批次 completed 且尚未关联申请时才启用学生提交按钮**。

| 批次状态 | 前端说明 | 允许的主要动作 |
| --- | --- | --- |
| `queued` | 排队识别 | 查看、继续轮询，不能提交 |
| `processing` | 正在识别 | 查看、继续轮询，不能提交 |
| `completed` 且 `application_id == null` | 本轮识别结束，逐行可能有异常 | 学生选择可提交行；符合条件时重试或整批修正类型 |
| `failed` 且 `application_id == null` | 批次租约多次超时等失败 | 停止轮询；有failed/incomplete项时显式重试 |
| `submitted` | 已提交待审核 | 停止识别轮询；学生只读，教师/管理员审核 |
| `approved` | 已认定 | 展示实际入账分；教师/管理员可重新核定或撤销 |
| `rejected` | 已驳回或撤销 | 展示零入账分，保留证据；当前没有重新打开/重新提交接口 |

`completed` 不等于“全部有效”或“自动通过”。整批没有可提交行时显示各行原因，而不是提交空数组。已驳回记录不能用新上传或重试恢复资格；重新认定流程尚需明确设计，前端不能自行改变状态。

| 明细状态 | 表格提示 | 学生选择/处理 |
| --- | --- | --- |
| `queued` | 等待本轮OCR处理 | 不可选 |
| `ready` | 已提取，等待申报/核查 | 仅在批次可提交且 `can_submit === true` 时可选 |
| `incomplete` | 时数/记录标识不完整或数值无效 | 不可选；允许条件下重试，必要时补充材料 |
| `failed` | 图片读取或模型执行失败 | 不可选；允许条件下重试 |
| `wrong_type` | 截图类型与本批选择不符 | 不可选；学生纠正整个未提交批次类型 |
| `duplicate` | 重复图片/活动或明确跨类型重复 | 不可选；展示 `duplicate_of`，不能重试解禁 |
| `approved` / `rejected` | 已核定明细 | 作为审核结果展示，不代表可以重新申报 |

批次详情中的 `can_submit` 只表示行级资格，并不包括整个批次的所有状态约束；已提交/批准明细可能仍返回true。复选框必须同时校验学生角色、`status === 'completed'`、`application_id === null` 和行级 `can_submit`，不能只依据这一布尔字段。

### 6.6 预览数据结构与字段展示

上传、详情、提交、重试、类型修正、审核成功都直接返回同一类批次预览对象。概要列表和政策接口不是这个结构，不要共用同一个解析假设。以下是一个信用批次的示意响应，`fields` 仅摘录时数字段，其余字段见后文：

```json
{
  "id": 101,
  "material_type": "volunteer_credit",
  "year": 2026,
  "status": "completed",
  "version": 2,
  "application_id": null,
  "policy": {
    "revision": 1,
    "credit_rate": "0.01",
    "honor_rate": "0.01",
    "max_score": "2",
    "honor_enabled": true,
    "start_date": "2025-09-01",
    "end_date": "2026-08-31",
    "rounding": "HALF_UP_4"
  },
  "rows": [
    {
      "id": 501,
      "filename": "credit.png",
      "status": "ready",
      "displayed_hours": 5.05,
      "claimed_hours": "5.0500",
      "requested_hours": "5.0500",
      "confirmed_hours": null,
      "credit_max_hours": "15",
      "activity_name": "志愿服务活动",
      "activity_dates": ["2025-12-21"],
      "check_in": "2025-12-21T12:33:03",
      "check_out": "2025-12-21T17:36:34",
      "recorded_at": null,
      "fields": {
        "displayed_hours": {
          "value": 5.05,
          "ocr_confidence": 0.99,
          "evidence": [{"text": "+5.05", "confidence": 0.99, "box": [330, 400, 590, 500]}]
        }
      },
      "estimated_score_before_cap": "0.0505",
      "duplicate_of": null,
      "can_submit": true,
      "warnings": [{"code": "identity_unverified", "message": "此实验不验证截图是否属于申报学生"}],
      "error": null,
      "submitted": false,
      "cross_type_conflicts": [],
      "image_url": "/api/automation/items/501/image"
    }
  ],
  "estimated_incremental_score": "0.0505",
  "final_score": null,
  "remaining_batch_id": null,
  "source_batch_id": null,
  "note": "未批准批次为条件估算，实际认定以审核结果为准"
}
```

| 字段 | 类型/含义 | 前端对齐要求 |
| --- | --- | --- |
| `id`、`version`、`year` | 整数 | ID用于路由，version用于防旧请求覆盖，year为政策年度 |
| `material_type` | `volunteer_credit` / `volunteer_honor` | 响应使用完整名称，上传表单/类型修正使用credit/honor短名 |
| `application_id` | 整数或null | 非空表示已关联旧申请，不等于batch ID |
| `policy` | 政策对象或null | 批次已提交时为其冻结政策快照，展示时优先于另外GET到的政策 |
| `rows` | 明细对象数组 | 用row.id作为稳定key，不能用filename或数组下标 |
| `displayed_hours` | 通常数字；识别异常时可能是原始字符串或null | 截图原始显示值，不用15小时规则改写，不盲目Number转换异常原文 |
| `claimed_hours` | 小数字符串或null | 上传时保存的显式申报值，不能用它代替requested_hours |
| `requested_hours` | 小数字符串或null | 学生本次申请值，信用含15小时截限，荣誉按截图值 |
| `confirmed_hours` | 小数字符串或null | 核定后才有，拒绝的已提交行可为零；未审核不是0 |
| `credit_max_hours` | 信用为字符串`"15"`，荣誉为null | 荣誉不能误套信用上限 |
| `activity_dates` | `YYYY-MM-DD`字符串数组 | 直接展示多个日期，空数组显示“待教师补充”，不能填录入日期 |
| `check_in/check_out/recorded_at` | ISO日期时间字符串或null | 前两项是签到签退，最后是平台录入；无时区偏移的值按源平台时间展示，不自动当UTC转换 |
| `fields` | `{字段名: {value, ocr_confidence, evidence}}` | 用于字段级证据；空值和低置信度分开标记 |
| `estimated_score_before_cap` | 四位小数字符串或null | 每行未封顶建议分，不能相加冒充精确批次入账值 |
| `estimated_incremental_score` | 四位小数字符串或null | 未审核为当前条件估算；批准后为实际批次入账；驳回为零 |
| `final_score` | 四位小数字符串或null | 未审核null、已批准实际入账、已驳回零；必须与预计分区分 |
| `submitted` | 布尔 | 审核只针对true的明细，不能提交重复等未申报行的审核决策 |
| `duplicate_of` | 明细整数ID或null | 指向原材料，不是原批次或申请ID |
| `warnings` | `{code, message}`数组 | 提示不都意味着禁止提交，资格以行/批次状态为准；不得统统过滤隐藏 |
| `cross_type_conflicts` | 冲突对象数组 | 结构见6.8；明确重复和待人工核查要区分 |
| `error` | 文本或null | 本行执行失败/字段异常原因，不等于HTTP请求错误 |
| `image_url` | 受保护的相对URL | 加载原图用，不改写为/uploads路径 |
| `remaining_batch_id/source_batch_id` | 批次整数ID或null | 部分提交产生的父子关联，提供继续处理/返回来源按钮 |

信用表建议列：选择、原图、识别时长、申请时长、签到、签退、活动名称、活动日期、预计加分、状态/异常。荣誉表建议列：选择、原图、识别时长、申请时长、志愿者姓名、录入时间、录入类型、录入原因、实际活动日期、预计加分、状态/异常；录入人和组织可放详情抽屉。荣誉专属字段从 `row.fields.volunteer_name/recorder_name/recording_organization/record_type/record_reason?.value` 中取，不能假定这些都有顶层同名字段。信用没有荣誉身份字段属于不适用，不表示截图无效。

显示数值时区别null和0，避免 `value || '--'` 吞掉零。小时和分值优先保留服务端字符串；前端浮点计算仅作非权威展示，不能把toFixed结果传作最终分数。OCR文本及审核意见作为不可信纯文本展示，不直接用v-html渲染。

原图可在同域通过 `<img :src="row.image_url">` 展示，网络失败需提示无权限/会话过期并允许重新登录；若采用fetch读取Blob，带cookie且及时回收object URL。证据接口只在展开时请求，避免每次轮询加载全部OCR。`fields[*].evidence`中的每项是 `{text, confidence, box: [x1,y1,x2,y2]}`；叠加框按原图尺寸与实际显示尺寸换算。OCR分数是识别置信度，不是“截图真实性概率”。

### 6.7 学生提交、版本控制与剩余批次

1. 从最新详情中选取允许提交的明细ID，前端显示当前选择数量；显式传 `item_ids`，不能把未选中的行靠省略字段一并提交。
2. POST提交时传当前整数version，设置 `submitting` 锁，暂时暂停轮询或隔离过期响应，避免轮询覆盖新提交结果。对同一批次的重试、类型修正、提交和审核不要同时发送。
3. 收到201后直接采用响应里的新version、submitted状态及application_id，跳转申请详情或显示“待审核”，不要再额外调用旧 `POST /api/applications` 创建第二份申请。
4. `remaining_batch_id`非空时给出“继续处理剩余材料”入口，打开该批次并请求其详情；正常未选中行、失败/不完整行和错类型行可能都在子批次。重复行留在原批次，不在子批次解禁。子批次正常行可以继续提交，异常行按重试/类型修正处理，不能要求学生原图全部重传。
5. 409时清空旧选择中已失效的ID，重新GET详情提示状态变化，让用户再次确认；不要自动递增version、猜测version或自动重试POST。超时后先查询是否已有application_id，确认成功则展示已提交，不再次创建。

当前没有“按当前勾选子集试算精确加分”的GET/POST接口。提交前 `estimated_incremental_score`按整批可计行估算，不会随前端勾选自动变化；前端可以提示“整批估算，选中部分以提交返回为准”，或者展示“所选行未封顶参考值”，但不能冒充后端精确封顶值。提交成功响应会返回选中行对应的后端权威估算。若产品必须在提交前精确试算部分行，应新增只读试算接口，而非读取并相加舍入后的行分数。

### 6.8 教师审核：旧申请列表接入新明细

旧申请对象仍使用驼峰字段，自动化预览使用下划线字段，不能混在同一对象中猜测：

| 语义 | 旧Application返回 | 新批次返回 |
| --- | --- | --- |
| 关联入口 | `dynamicCoefficients.automation_batch_id` | `id`及`application_id` |
| 状态 | 待审核为`pending` | 待审核为`submitted` |
| 学生建议分/当前条件估算 | `selfScore`（提交时的值） | `estimated_incremental_score`（当前条件或实际值） |
| 最终入账分 | `finalScore`，通常JSON数字 | `final_score`，四位小数字符串或null |
| 类型 | `applicationType: 'comprehensive'` | `material_type: 'volunteer_credit/volunteer_honor'` |

审核列表检查 `application.dynamicCoefficients` 中是否含 `automation_batch_id`。有该标记时打开专用明细审核面板并GET批次，不走旧“直接填写finalScore”的弹窗。旧对象的 `files` 在新自动化申请中为空是正常情况，原图在批次rows里；不要显示成“无材料申请”。无标记的人工申请保留原审核逻辑。建议调用专用 `/api/automation/.../review`；兼容的旧 `/api/applications/{application_id}/review`也必须传同样的新版明细对象。

审核表以 `rows.filter(row => row.submitted)` 为全集，每行提供通过/拒绝、核定小时、活动实际日期及核查意见。通过的信用行默认核定 `requested_hours`、日期保持截图签到签退日期，只允许调整小时且不得超过15；通过的荣誉行默认小时来自requested_hours，日期缺失须教师根据来源资料补充。被拒绝行可以仅提交id、decision和comment；不要把未提交的重复行纳入审核对象。整批通过请求至少一行通过，全部拒绝时改用整批 `status: 'rejected'`。

意见规则：核定小时不同于截图显示值、姓名不符、时长/申报冲突、任一字段低置信度、补充/修改荣誉日期或人工排除疑似跨类型冲突时，行comment必须填写实际核查依据；全局reviewComment不能代替行comment。信用截图超过15时默认核定15，仍与显示值不同，需要写明截限依据。缺少活动日期的荣誉行可能允许学生提交，但没有核定实际日期不能批准。

冲突对象示例：

```json
{
  "id": 610,
  "activity_dates": ["2025-12-21"],
  "activity_name": "待核对活动",
  "status": "approved",
  "match": "needs_verification",
  "blocking": false
}
```

- `blocking: true`是明确重复，禁止通过；不能用“已查看原图”复选框放行。`match: 'same_activity'`但blocking为false也应展示优先级提示，后端会保护先上传/已提交记录，不能把字段含义扩展为“已证明不是重复”。
- `match: 'needs_verification'`时，显示冲突活动日期、ID以及对方原图/证据供逐项核查。只有教师确认确为不同活动后，把这些冲突明细ID加入通过行的 `distinct_activity_ids`，并写明依据。数组需与当前所有疑似冲突ID完全一致，无重复、无多余ID；没有疑似冲突时用空数组或省略。不要自动预选或无人工判断地自动填满。
- 核定小时建议用小数字符串，活动日期传 `YYYY-MM-DD`数组；全部明细ID及distinct_activity_ids必须是整数，不是字符串。若组件返回字符串ID，应在确保是合法正整数后转换，而不是对任意输入直接Number处理。

通过请求示例（batch 101，实际version以最新GET为准）：

```json
{
  "version": 3,
  "status": "approved",
  "reviewComment": "已完成材料核查",
  "items": [
    {
      "id": 501,
      "decision": "approved",
      "confirmed_hours": "5.05",
      "activity_dates": ["2025-12-21"],
      "distinct_activity_ids": [610],
      "comment": "核对两份平台活动详情，确认同日但不同活动"
    },
    {"id": 502, "decision": "rejected", "comment": "材料不足，未予认定"}
  ]
}
```

该示例假设两行都已经submitted、当前501的唯一疑似冲突为610；不能照抄固定ID。整批驳回/撤销只需 `{version, status: 'rejected', reviewComment}`，不需要伪造confirmed_hours。审核成功后采用返回的final_score，刷新申请详情、成绩汇总和相关年度批次数据；撤销可能改变其他已批准批次的上限分配，不能只把本地这一行改成零。已批准批次可再次核定或撤销，已驳回批次目前不接受再审核。

接口缺口必须明确：当前没有接收“拟核定activity_dates”并返回新冲突列表的审核预检接口。教师在本地补日期不会改变GET预览，提交失败会回滚新增日期；如果补日期后出现原预览没有的跨类型疑似冲突，仅刷新原GET也不能得到按拟定日期计算的冲突ID。此场景应先由团队补充只读审核预检契约及前端核查交互，或由审核人结合完整来源材料人工核查后提供准确ID；不得把现有页面当作已支持无缺口的补日期自动核查流程，不得猜ID、去掉校验或自动放行。当前错误返回也没有结构化的新冲突ID清单。

### 6.9 错误处理、状态恢复与按钮约束

| HTTP/场景 | 前端动作 |
| --- | --- |
| 400 | 展示服务端error/message；检查表单、数值、日期、审核意见及明细全集，保留用户输入用于修正 |
| 401 | 停止轮询，提示会话失效并进入登录；重新登录后GET服务端最新状态，不自动重复提交 |
| 403 | 提示角色或学院无权限；隐藏不属于该角色的操作，不通过改请求体中的学生/学院ID重试 |
| 404 | 材料/批次不存在或图片不可用，返回列表或提示重新查询；不是所有404都代表没有接口 |
| 409 | 查看具体原因：旧version/状态改变、政策冻结、重复活动或不允许的修改；刷新最新详情并再次确认，不统一弹“网络错误” |
| 413 | 文件或总请求过大；若代理返回HTML也要友好提示，压缩或减少图片后重新选择 |
| 5xx/网络中断 | 提示服务不可用、保存未提交表单；先查询服务端状态，禁止无条件自动重发POST |
| 用户主动取消GET | 静默停止当前等待，不显示为材料识别失败 |
| `REQUEST_TIMEOUT` | 提示本地等待超时，不代表服务器未执行；按6.3先查询/找回已知批次 |

400/409当前只有文本原因，不提供稳定业务错误码或逐字段错误对象；应根据HTTP状态和刷新后的真实状态处理，避免把中文message匹配写成核心流程。不要把GET到的version当成永不变化的常量。网页禁用按钮只是交互约束，不是权限保障，后端仍会验证所有操作。

旧接口的自动化申请更新/删除保护有时返回Flask默认的非JSON错误页，前端请求层也需容错。自动化申请不要显示普通“编辑finalScore/删除申请”入口；驳回/撤销走审核，不能物理删除去重和审计记录。用户及组织删除出现409时显示材料保留原因并建议停用账号，不以清空截图解决。

### 6.10 前端联调验收清单

- 确认维护的前端目录、代理端口、同源cookie；学生本人、本学院教师/管理员和外院账号分别验证401/403及角色按钮。
- 信用/荣誉分别上传单张与多张，检查FormData字段、数量/大小限制、claimed_hours与文件顺序；荣誉不得误套15小时上限。
- 上传202后正确轮询，显示queued/processing到completed；离开页面无残留轮询，切换批次不被旧响应覆盖；全重复响应不一直等待识别。
- 已验证样本的识别值、空值、日期、多行原因和OCR证据能正确展示；录入时间与实际活动日期明显区分，不把null渲染成0。
- 验证信用原图超过15仍保留原时数、默认申请15；显式申报/核定超过15失败，截限后审核要求依据。
- 同文件、修改图片但同活动、荣誉日期换序以及明确跨类型重复不可提交；疑似冲突不能未人工核查就默认勾选放行。
- 混合正常/重复/失败/错类型行进行部分提交，201后不再创建第二份Application；remaining_batch_id中的材料ID及原图保持不变，能继续提交或按权限重试/修正类型。
- 上传后的申报值只读；所选子集预计分不是精确封顶承诺；没有审核预检接口的补日期场景按6.8明确限制，不伪装成已完成的能力。
- 旧申请列表识别dynamicCoefficients.automation_batch_id；pending与submitted区分，新申请files为空不被当作缺材料；审核明细覆盖全部submitted行。
- 审核通过、部分拒绝、整批驳回、撤销和年度上限重算后，批次实际入账与旧申请finalScore、成绩汇总一致；分值字符串不被浮点相加替代后端结果。
- 重复点击、两个标签页同时操作、旧version、响应丢失、401、409及非JSON的413/5xx均有明确处理，不猜版本或自动重复写入。
- 管理员政策缺失/荣誉禁用/政策冻结均有说明；私有原图在无会话或跨权限时不可访问；页面不公开映射private-materials。

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
