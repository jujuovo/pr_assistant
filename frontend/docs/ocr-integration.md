# OCR 前端接入记录

请求模块：`src/services/volunteerApi.js`。已覆盖政策读写、批次上传/列表/详情、原图地址、证据、重试、类型修正、提交和逐项审核。使用真实后端及 Session Cookie，不提供模拟 OCR。

```js
import volunteerApi from '@/services/volunteerApi.js'

const form = new FormData()
form.append('material_type', 'credit')
form.append('year', '2026') // 使用实际政策年度
for (const file of files) form.append('files', file)
const batch = await volunteerApi.upload(form)
const latest = await volunteerApi.getBatch(batch.id)
```

页面尚未接线。后续需实现：上传表单、串行轮询 queued/processing 状态、结果预览及选择、最新 version 提交、教师逐项审核。离开页面停止轮询并通过 AbortSignal 取消查询；遇到 401 停止查询并重新登录，409 刷新详情后重新确认。任何写请求都不会自动重试；上传响应丢失时查询列表人工确认，避免重复上传。

不要手动设置 multipart Content-Type，不要再次拼接 /api。原图使用后端 image_url 或 getImageUrl，不走 JSON 解析。审核 items 必须覆盖已提交明细，遵守后端日期及冲突核查规则，不能只传 finalScore。

启动：backend 中分别运行 app.py 和 recognition_worker.py；frontend 中运行 npm run dev，禁止用 demo 联调。先准备 Python/OCR 依赖、测试数据库及数据库迁移；Web 与 worker 共用数据库和材料目录。

完整接口契约见 ../../backend/docs/volunteer-automation.md。当前仅完成请求层，不表示已通过真实后端或 OCR 端到端验收。
