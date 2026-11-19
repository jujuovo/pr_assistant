# PR #2 前端目录冲突修复

以 main 的 frontend/src 结构为准，将证书项目选择、申报字段和识别报告接入新版申请表及公共详情弹窗。旧 frontend/components 和 frontend/utils 中的冲突文件保持删除。CertificateSelection 与 CertificateReport 移入 src/components，统一使用 @/services/api.js。请求错误兼容后端 error 字段。

表单初始化、重置、草稿/申请提交和详情回填保留 certificateProject、certificateClaims。证书识别仍为审核辅助，不自动加分。五类材料仍仅有 PR 提供的后端核验接口，不新增五类页面或 OCR 能力。后端代码与原 PR head c0b14ca 一致。

## 验证（2026-10-14）

- 前端 npm run build 通过；仍有包体积超过 500 kB 的提示。
- 使用真实 Pinia 申请 store 和模拟 HTTP 响应，验证 certificateProject/certificateClaims 经 multipart 提交与详情读取不丢失。
- backend: python -B -m pytest tests -q -p no:cacheprovider：166 passed, 2 skipped，65 warnings。
- 无未解决冲突、无新增冲突标记；迁移顺序为 20261012_auto → 20261013_certificate → 20261013_materials。

本次环境为 macOS、Node 26.10.0、Python 3.14.7，临时安装后端测试依赖（并非 Windows 锁定版本环境）。没有安装 Paddle 模型，未启用真实 OCR 测试；Windows 启动、真实图片识别与生产 PostgreSQL 迁移仍需在目标环境验证。本次没有启动生产服务或修改业务数据库。
