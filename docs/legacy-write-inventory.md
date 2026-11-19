# 旧申请与成绩写入点清单

此清单是渐进迁移的门禁。所有旧写入点必须逐项接入统一用例并保留兼容投影，清单归零前不得删除 `Application` 或 `Student` 旧字段。

| 文件 | 当前写入 | 目标用例/投影 | 退场条件 |
| --- | --- | --- | --- |
| `backend/blueprints/application_bp.py` | 创建/编辑/审核/删除 `Application`，直接写 status、final_score 并调用旧汇总 | 审核改调统一认定与计分用例；旧字段由兼容投影写入 | 所有旧客户端迁移、回归通过、对账无差异 |
| `backend/blueprints/automation_bp.py` | 志愿批次提交时创建 `Application` | 保留批次来源，最终认定改调统一计分端口 | automation 全套回归和历史批次对账通过 |
| `backend/services/automation.py` | 写 Application status/final_score，调用旧汇总 | 统一计分用例写 ScoreEntry，Application 仅兼容投影 | 撤销与年度重算均以 ScoreEntry 为权威 |
| `backend/services/certificates/preview.py` | 证书预览创建草稿 Application | 保留预览模型；确认/审核接入统一认定端口 | 证书预览和人工审核回归通过 |
| `backend/use_cases/certificates.py` | 证书兼容来源的审核状态与 `final_score` 投影 | 通过统一审核计分用例产生权威事实，并仅在同一事务中更新旧投影 | 证书旧读取归零且连续对账一致 |
| `backend/use_cases/scoring.py` | 在统一事务内更新 `Application.final_score` 兼容投影 | `ScoreEntry` 与 `StudentScoreSnapshot` 为权威，旧字段仅随统一结果投影 | 旧读取归零且连续对账一致 |
| `backend/blueprints/score_bp.py` | 从 approved Application 汇总并直接写 Student 汇总、major_ranking | StudentScoreSnapshot 与 RankingBatch 为权威，旧字段只读投影 | API/前端不再读取旧字段，连续对账一致 |
| `backend/utils/rule_engine.py` | 仅使用临时 Application 形状计算，无数据库写入 | 后续替换为纯规则输入 DTO | 没有调用者依赖 ORM 形状 |
| `backend/tools/validate_postgres_backfill.py` | 仅在显式隔离的 PostgreSQL 验证库中构造带 `final_score` 的历史申请，用于验证修复中断续跑 | 不属于生产入口；通过 `DATABASE_URL` 与 PostgreSQL 方言双重门禁限制在验证环境 | PostgreSQL 修复演练完成后保留为发布验证工具，不计入活跃生产消费者 |

### `finalScore` 兼容监测

`POST /api/applications/{id}/review` 收到旧 `finalScore` 时记录结构化警告
`legacy_final_score_request`，包含申请、操作者以及是否携带理由，不记录证明材料原文。
证书统一审核路径仅在操作者已有本学院审核权限且同时提供非空 `overrideReason` 时，
把 `finalScore` 转换为显式 `override_score/override_reason`，并写入 `ScoreOverrideAudit`。
缺少理由返回 `legacy_final_score_requires_reason`；尚未接入统一来源的旧申请返回
`legacy_final_score_not_supported`，不得继续静默覆盖规则自动分。

监测搜索：

```powershell
rg -n "application\.(status|final_score|self_score)\s*=|Application\(|update_student_statistics\(|comprehensive_score\s*=|major_ranking\s*=" backend -g "*.py"
```

测试与迁移文件中的构造不属于生产写入口，但需要随模型兼容期保留。新生产代码不得新增未登记的旧字段写入点。

## 弃用与退出门槛

运行期监测必须按 `application_api`、`score_api`、`certificate_preview`、`volunteer_automation`
记录旧契约调用量。只有活跃消费者为零、迁移差异为零、至少连续两次完整对账无差异且备份已验证时，
`legacy_exit_gate` 才允许另立变更删除旧字段。当前变更只收紧写入并保留历史数据，不执行字段或表删除。

监测按消费者分别记录读写请求数：`application_api`（读/写）、`score_api`（读）、
`certificate_preview`（写）、`volunteer_automation`（写）。门禁输入必须包含全部消费者；缺项、任一计数
非零、未知消费者、对账差异非零、连续一致少于两次、备份未验证或 automation 回归未通过都会阻止退场。

