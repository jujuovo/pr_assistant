# 旧 Application 链路退出记录

> 结论先行：**新功能不要再和 `Application` 产生任何联系**。
> 旧链路保存的是「结果」（`self_score` / `final_score` + 一个指向可变 `Rule` 的指针），
> 保存不了「依据」；规则一旦修改，历史分数无法解释来源，因此**不可复算**，
> 这也正是它无法支撑自动计分的原因。

## 一、当前状态（2026-11-21）

### 已迁到 `MaterialRecord` 链路的类别

`competition`、`volunteer`、`social_practice`、`research_paper`、
`innovation_training`、`student_work`、`arts_sports`

这些类别的前端入口全部走 `materials` 或专用的竞赛工作台，
后端写入口已由 `blueprints/application_bp.py` 的 `MIGRATED_MATERIAL_ROUTES` 拦截：
新建旧申请返回 `409`，并带上 `code` 与新入口 `route`。

### 仍走旧链路的类别

`academic`（学业成绩）、`language`（外语能力）、`honor`（荣誉称号）、
`certification`、`research`、`competition_evidence` 等尚未迁移类别。
这些类别继续使用 `Application + Rule`，属于兼容态，**不得写入已迁移类别**。

## 二、依赖清单（物理删除前必须处理）

| 位置 | 依赖方式 | 物理删除 `application` 的后果 |
| --- | --- | --- |
| `material_models.py:11` | `MaterialRecord.application_id` 外键（可空） | 变成孤儿，外键开启后被拦 |
| `automation_models.py:28` | `AutomationBatch.application_id` 外键（唯一） | 志愿批次失去关联 |
| `certificate_models.py:9` | `CertificateAssessment.application_id`（**`ondelete="CASCADE"`**） | **静默级联删除证书评估记录** |
| `workflow_models.py:591` | `LegacyBackfillItem.application_id`（非空外键） | 直接删除失败 |
| `use_cases/scoring.py` | `adapt_legacy_application`，`source_type='legacy_application'` | 已生成分数失去来源解释 |
| `services/automation.py:397` | 读 `application.final_score` 计算志愿年度增量 | 志愿上限分配失效 |
| `blueprints/application_bp.py` | 135 处引用（列表、审核、统计、导出） | 大面积 500 |
| `frontend/src/stores/applications.js`、`pages/admin/applications/ApplicationManagement.vue`、`pages/student/applications/ApplicationHistory.vue` | 历史查询、编辑、删除 | 历史页不可用 |

**最大风险是 `certificate_assessment` 的 `ondelete="CASCADE"`**：
删除 `application` 行不会报错，而是把证书评估一并删掉，事后无法恢复。
在收紧该外键（改成 `RESTRICT`）之前，禁止任何批量删除 `application` 的操作。

## 三、退出步骤（分三段，不要跳步）

### 阶段 1：堵住新写入（已完成）

- `POST /api/applications` 对已迁移类别返回 `409`，覆盖"带 `rule_id`"和"只带 `application_type`"两种请求；
- `GET` / `PUT` / `DELETE` 保持不变，历史查询与旧申请清理仍可用；
- 回归测试：`backend/tests/test_legacy_application_exit.py`。

### 阶段 2：业务退出（待排期）

1. 志愿工时批量提交与证书 OCR 改为直接写 `MaterialRecord`，不再创建 `Application`；
2. 首页统计、学生记录、教师待审/历史、统计页面改为只读 `MaterialRecord`；
3. 旧数据分级迁移：草稿/待审/待补正 → `MaterialRecord`；已计分 → `MaterialRecord + ScoreEntry` 并保留来源映射；已拒绝/已撤回 → 保留只读历史；无法映射的进人工对账清单。

### 阶段 3：只读观察 → 物理删除

物理删除的前置条件（全部满足才可执行）：

- 已迁移类别只写 `MaterialRecord`；
- `Application` 新增记录连续为 0；
- 历史有效分全部有 `ScoreEntry` 与可解释来源；
- 证书 OCR、志愿批量不再引用 `application_id`；
- 首页、教师审核、统计、排名不再查询 `Application`；
- 依赖外键已迁移或改写。

## 四、本地环境注意事项

- SQLite 外键约束已在 `backend/extensions.py` 中默认开启（`foreign_keys=ON`、`journal_mode=WAL`），
  因此"被依赖的记录删不掉"从配置层面真实生效；
- 测试环境通过 `SQLITE_FOREIGN_KEYS=0` 关闭外键，因为多个用例刻意构造孤儿数据验证容错路径；
  需要用外键跑整套回归时：`$env:SQLITE_FOREIGN_KEYS='1'; pytest`；
- WAL 模式下备份必须连同 `-wal` 文件一起复制，否则会丢最近的事务。
