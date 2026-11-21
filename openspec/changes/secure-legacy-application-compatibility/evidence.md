# 验证记录（2026-11-21）

## 已执行

- 新增安全及迁移用例：37 passed；权限、身份伪造、跨学院/跨学生、历史只读、首次审核与重复审核、原/新规则、历史计分、文件提交失败、ORM加载/未加载两种父删除、迁移往返/索引/唯一性/孤儿保护。
- 定向兼容回归：96 passed。命令：`.venv/Scripts/python.exe -B -m pytest backend/tests/test_automation_lifecycle.py backend/tests/test_material_interfaces.py backend/tests/test_legacy_application_write_security.py backend/tests/test_certificate_restrict_upgrade.py -q -p no:cacheprovider --tb=short`。
- 完整后端：`.venv/Scripts/python.exe -B -m pytest backend/tests -q -p no:cacheprovider --tb=short` → **855 passed, 4 skipped**（169.06秒）。日志：`backend/outputs/legacy-full-tests-final.log`。跳过未视为通过，现存SQLAlchemy弃用/统计事件告警未宣称修复。
- 独立新库：`.venv/Scripts/python.exe -B backend/tools/prepare_local.py --database-file backend/outputs/legacy-fresh-20261121.db`。成功创建共享三角色、2028周期、正式竞赛current规则包及28项目录。
- 在真实app配置和隔离新库上用Flask test_client执行兼容外语申请：匿名创建401，本人草稿创建201/编辑200，迁移竞赛类别编辑409，提交200，同院首次审核200，重复审核409，历史读取200，已处理修改/删除409。此为接口/state smoke，不是浏览器验收。外语规则未由prepare准备，审核返回needs_rule且不产生正式外语加分；本轮不实现外语政策引擎。日志和复现脚本：`backend/outputs/legacy-fresh-api-smoke.log`、`backend/outputs/legacy-api-smoke.py`（本地忽略的实验产物）。
- 一致性副本演练：`.venv/Scripts/python.exe -B backend/tools/check_legacy_application_upgrade.py --source backend/instance/gradpush-dev.db`。只读源库，副本位于`backend/outputs/legacy-upgrade-20261121-223114-543708.db`；未命名CASCADE改为命名RESTRICT，两次调用幂等，所有表行数/摘要一致，foreign_key_check=0。报告：`backend/outputs/legacy-upgrade-rehearsal.json`。源库application/certificate_assessment均0行，非空证据保留另由SQLite真实约束用例验证，不把空表演练当作真实历史证据迁移证明。
- 已重启本聊天启动的Web进程加载代码，沿用原gradpush-dev.db（未迁移）；worker与前端保留。HTTP检查：`/api/public/system-info` 200，5173首页200，未登录POST /api/applications 401。
- 工作区差异检查采用`git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --check`；application_bp.py保留Git中原有CRLF，避免全文件换行差异。

## 边界与待验收

- 未对原开发数据库应用升级；副本工具不更新alembic_version，不能替代正式`flask db upgrade`。部署前须停写/备份、确认迁移版本并升级实际数据库，复核外键和证据摘要。
- 没有真实PostgreSQL环境，未执行其约束升级、锁/并发或回滚验证；不能声称PG验收通过。
- 未自动化浏览器，不代用户勾选。手工建议3项：学生正常材料申报仍可使用；本人兼容历史详情可查看而已处理不可改写；教师审核完成后历史再审核有明确拦截。
- 本轮未改前端代码；之前低风险维护的mounted/Node/build证据仍由repair-material-low-risk-maintenance持有，不重复认领。
- OpenSpec CLI缺失，list/status/apply未成功；未执行CLI严格校验，未同步主spec、未归档。
- 保留旧宿主、旧表、旧查询；本轮完成风险收紧，不等于业务完整退出。未提交或推送代码。
