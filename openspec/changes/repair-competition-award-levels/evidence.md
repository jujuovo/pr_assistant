# 验证（2026-11-23）

- 权威来源：docs/policies/xmu-informatics-2025-02.pdf，渲染检查第5、6、15页。第6页第（6）条明确国家级赛事省级获奖按同类省级标准计分。
- 首轮目录/材料校验17 passed，覆盖真实API的选项、上下文、省级一二等奖预估0.3333/0.1667（A-个人项目按1/3）、省三等奖400、材料保存201及快照不变。
- 全部test_competition*.py回归170 passed，结果见backend/outputs/award-levels-competition-regressions.log。
- 前端competition-workflow.mounted.test.js：38 passed；实际挂载蓝桥杯表单，验证两级选项、省级无三等奖、切换级别清空无效奖项、预估请求传入provincial事实。
- 前端生产构建通过，保留既有chunk大小提示。构建和挂载不代替真实浏览器验收；不声称业务数据库升级或页面端到端已通过。
- 不修改发布快照、不重算历史、不创建数据库迁移。本轮修复为后端政策解释与选项投影，存量国家级奖项分值不变。

## 2026-11-23 目录刷新回归修复（归属本变更）

- 根因：CompetitionWorkflow.retry 用通用上下文 field_schema 覆盖赛事专属 schema，已选赛事未重新加载，级别和奖项因此只剩占位选项。
- 修复：刷新时重新请求当前赛事详情并统一更新上下文和专属 schema；保留合法级别、奖项和未保存的草稿编辑，仅清除新版 schema 不再支持的选项；请求失败保留原表单，加载期间禁止重复刷新。
- `cd frontend; npm.cmd run test:mounted -- tests/competition-workflow.mounted.test.js`：42 passed。新增挂载交互覆盖通用 schema 缺少选项、刷新后省级奖项可选、失败重试、草稿未保存编辑保留和失效奖项清除。
- `cd frontend; npm.cmd run build`：通过；`git diff --check`：通过。
- 未执行真实浏览器和真实后端旅程；由用户手动验收：选赛事及级别奖项后点击刷新，确认选项与填写内容保留；编辑草稿修改项目名后刷新，确认修改保留。本记录不将浏览器验收标为通过。
