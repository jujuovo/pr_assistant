# 验证记录（2026-11-20，Windows）

## 备份与分支

- 备份标签：`backup-pre-arts-sports-20261120`（指向修改前 HEAD `701d80b`）。
- 源码备份：`D:\pr_assistant\backups\pr_assistant-pre-arts-sports-20261120.zip`（`git archive HEAD`，3.8 MB）。
- 工作分支：`feature/arts-sports-material-20261120`。

## 自动化验证

| 检查 | 命令 | 结果 |
|---|---|---|
| 新增后端测试 | `pytest backend/tests/test_arts_sports_material.py -q` | 11 passed |
| 材料接口/OpenAPI | `pytest backend/tests/test_arts_sports_material.py backend/tests/test_material_interfaces.py backend/tests/test_ocr_material_fields.py -q` | 80 passed |
| OpenAPI 示例校验 | `pytest backend/tests/test_ocr_material_fields.py -q` | 39 passed |
| 后端完整回归 | `pytest backend/tests -q -p no:cacheprovider` | 723 passed, 5 skipped |
| mounted | `npm --prefix frontend run test:mounted` | 82 passed, 1 skipped |
| 学生主页统计 mounted | `npm --prefix frontend run test:mounted -- tests/student-home-count.mounted.test.js` | 2 passed |
| 教师主页统计 mounted | `npm --prefix frontend run test:mounted -- tests/teacher-home-count.mounted.test.js` | 2 passed |
| 教师全部类别汇总 mounted | `npm --prefix frontend run test:mounted -- tests/arts-sports-material.mounted.test.js` | 6 passed |
| Node | `node --test frontend/tests/*.test.mjs` | 58 passed |
| 生产构建 | `npm --prefix frontend run build` | 成功（保留既有大包提示） |
| 本次 change 校验 | `openspec validate repair-arts-sports-material-workflow --strict` | valid |
| 主规格校验 | `openspec validate --specs --strict` | 7 passed |

## 覆盖行为

- 五个提交项均能创建文体活动手工草稿，`manual_only=true`，不生成 `ScoreEntry`。
- 非法提交项、项目名称过短/过长、缺少获得时间均在写入前被拒绝。
- 草稿在「我的材料」可见，可正式提交；提交前要求至少一份原件。
- 教师本学院可读取已提交文体活动材料，退回补充必须填写意见；外院教师和其他学生被拒绝。
- 退回后学生可编辑为新草稿并重新提交，教师可通过；版本过期写入返回 409。
- 前端入口从旧 `ApplicationForm` 改到材料工作台；表单显示五个提交项；我的材料可提交；教师端可选择「文体活动」核验并退回。
- 学生主页「已通过」份数同时汇总旧兼容申请与新材料：`verified`/`scored`/`verified_not_eligible` 计入已通过；`application_id` 非空、竞赛、草稿和已放弃记录不重复计入。
- 教师主页「非竞赛材料待审核」份数汇总本学院可审核新材料的 `submitted`/`under_review`，并与旧兼容申请待审数相加；竞赛新材料仍走竞赛工作台，外院材料不进入。
- 教师「其他材料人工核验」默认「全部类别」，汇总所有可核验类别；切换具体类别后过滤；核验和历史事件使用每条材料自身的类别。

## 本地服务

- 后端 `http://127.0.0.1:5001/api/public/system-info` → 200。
- 前端 `http://127.0.0.1:5173/` → 200；Vite `/api` 代理 → 200。
- Web 与 worker 共用 `backend/instance/gradpush-dev.db`；worker 已加载 PP-OCRv5 模型。
- 后端已重启并加载新增的 `/api/materials/student/summary` 与 `/api/materials/teacher/summary`；真实登录 `student001` 返回 `approved_count=2`、`submitted_count=2`，对应当前库中两条 `verified` 新材料。
- 真实登录 `teacher001` 读取教师统计返回 `completed_count=3, pending_count=0`；当前开发库 3 条材料均为 `verified`、没有 `submitted`，所以待审 0 是真实结果。新建并提交一条非竞赛材料后，该计数会增加。
- 服务保留运行，供用户手动完成浏览器验收。

## 浏览器首次尝试的环境问题

首次打开「提交文体活动」时页面提示“此类材料尚未开放”。检查发现 5001 端口同时存在两个后端监听：`2026-11-19 22:26` 启动的旧进程（PID 28516，旧代码，无 `arts_sports`）和本次 `22:34` 启动的新进程（PID 31700）。浏览器命中了旧进程。已停止旧进程；真实 HTTP 登录 `student001` 后 `GET /api/materials/types` 返回 200 且包含 `arts_sports` 及五个提交项。该问题属于本地遗留进程，不是本次代码或仓库其他人的改动。

## 明确未验证

- 真实浏览器三角色旅程与截图：任务 9.1 保留未勾选，由用户手动执行。
- 生产 PostgreSQL、生产部署/Nginx、macOS、移动端：本次未执行，不宣称通过。
- 未修改学业竞赛、学业成绩、志愿服务、社会实践、社会工作、学术创新、能力认证、目录外竞赛及旧 `Application` 兼容路径；完整后端与前端回归未发现这些类别失败。

## 既有问题（不属于本次变更）

`openspec validate --changes --strict` 总计 4 passed / 1 failed；失败项为既有的 `integrate-local-ocr-main`（MODIFIED delta 丢弃主规格场景），本次未修改该 change。
