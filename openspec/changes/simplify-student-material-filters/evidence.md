# 验证（2026-11-21）

- `npm.cmd --prefix frontend run test:mounted -- tests/competition-workflow.mounted.test.js tests/volunteer-ocr.mounted.test.js`：48 passed，其中9项新增筛选挂载交互用例；覆盖8选项无重复、7组跨类别筛选及原始status兜底、权限不变化、全部含未知状态、轮询完成后切换分组。
- `node --test frontend/tests/student-navigation-boundary.test.mjs`：4 passed，属于静态边界检查，不算浏览器或视觉验收。
- `npm.cmd --prefix frontend run build`：成功，现存大体积chunk提示保留；构建不代替UI验收。
- Git差异检查通过，保留原文件换行。本轮未改后端，无数据库升级或业务写入。
- 上一独立变更的隔离新库/API验收不认领为本次界面验收。未执行真实浏览器操作，由用户在已运行的5173页面手动复验；对应任务保持未勾选。
- 本地日志位于backend/outputs/material-filter-tests.log和material-filter-build.log。未提交或推送代码。
