# 蓝桥杯与五类材料前端接口

## 模块

- `src/services/certificateApi.js`：项目目录、申请识别结果、版本化重跑、受保护证据 URL。已接入 CertificateSelection 和 CertificateReport。
- `src/services/materialApi.js`：五类材料的类型、列表、创建、详情、修改、附件、提交、撤回、来源对照、审核、审计、CSV 预览、来源导入与查询、OpenAPI，以及预留 recognize 接口。
- `src/services/requestJson.js`：上述模块的请求封装。相对地址、Session Cookie、JSON/FormData、取消、超时、HTTP 状态及业务错误，不自动重试。

五类 category：academic / competition / language / student_work / honor。业务字段原样传给后端，不进行驼峰转换或自行计算加分。

## 示例

```js
import materialApi from '@/services/materialApi.js'

let record = await materialApi.createRecord('language', {
  year: 2026,
  data: {
    exam_name: 'CET6', language: '英语', score: 560, full_score: 710,
    test_date: '2025-12-20', certificate_no: '实际证书编号'
  }
})
record = await materialApi.uploadAttachments('language', record.id, record.version, files)
record = await materialApi.submit('language', record.id, record.version)
// 教师登录后读取最新详情，再核验；verified 不代表已加分。
record = await materialApi.getRecord('language', record.id)
record = await materialApi.review('language', record.id, record.version, 'verified', '已核对原件')
```

每次写操作后采用响应中的新 version；updateRecord(category, id, version, data) 完整替换 data，必须传全需保留的字段。列表使用 listRecords(category, {year, student_id, status, limit, after_id}, signal)，响应保留 next_after_id。

附件 URL 供链接使用，证书图片 URL 供 img 使用，不走 JSON 解析。权限仍由服务端 Session 校验。上传使用重复 files 字段，不手动设置 Content-Type。

错误提供 error.status、error.payload、可选 error.code。401 停止轮询并登录，409 获取最新状态后确认，501/recognition_not_implemented 表示五类 OCR 尚未实现。REQUEST_TIMEOUT 只表示本地等待超时，需查询状态，不能自动重发写请求；主动取消保持 AbortError。

五类业务页面尚未接入，本次是请求层实现。蓝桥杯新流程使用 certificateApi.createPreview(files) 上传并在提交前识别，CertificatePreview 展示可编辑申报表；confirmPreview(id, data) 保存草稿或提交同一申请。学生修改值直接作为申报值，OCR报告与原件独立保留。教师公共详情组件同时展示三者。旧申请结果保留。后端契约见 backend/docs/material-interfaces.md 与 certificate-ocr.md。

## 验证

在 frontend 目录执行：

```sh
node --test tests/material-api.test.mjs
npm run build
```

测试使用模拟 HTTP 响应，验证实际请求格式及异常行为；不代表真实数据库、OCR 或 Windows 联调已通过。
