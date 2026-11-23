# 验证（2026-11-23）

- 权威来源：docs/policies/xmu-informatics-2025-02.pdf，渲染检查第5、6、15页。第6页第（6）条明确国家级赛事省级获奖按同类省级标准计分。
- 首轮目录/材料校验17 passed，覆盖真实API的选项、上下文、省级一二等奖预估0.3333/0.1667（A-个人项目按1/3）、省三等奖400、材料保存201及快照不变。
- 全部test_competition*.py回归170 passed，结果见backend/outputs/award-levels-competition-regressions.log。
- 前端competition-workflow.mounted.test.js：38 passed；实际挂载蓝桥杯表单，验证两级选项、省级无三等奖、切换级别清空无效奖项、预估请求传入provincial事实。
- 前端生产构建通过，保留既有chunk大小提示。构建和挂载不代替真实浏览器验收；不声称业务数据库升级或页面端到端已通过。
- 不修改发布快照、不重算历史、不创建数据库迁移。本轮修复为后端政策解释与选项投影，存量国家级奖项分值不变。
