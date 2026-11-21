# 旧 Application 链路退出记录

> 结论先行：**新功能不要再和 `Application` 产生任何联系**。
> 旧链路保存的是「结果」（`self_score` / `final_score` + 一个指向可变 `Rule` 的指针），
> 保存不了「依据」；规则一旦修改，历史分数无法解释来源，因此**不可复算**，
> 这也正是它无法支撑自动计分的原因。

## 一、当前状态（2026-11-21）

### 已迁到 `MaterialRecord` 链路的类别

`competition`、`volunteer`、`social_practice`、`research_paper`、`invention_patent`、
`innovation_training`、`student_work`、`arts_sports`

这些类别的前端入口全部走 `materials` 或专用的竞赛工作台，
后端写入口已由 `blueprints/application_bp.py` 的 `MIGRATED_MATERIAL_ROUTES` 拦截：
新建/编辑旧申请返回 `409`，并带上 `code` 与新入口 `route`；同时检查原规则、拟绑定规则和类别字段，清空规则编号也不能绕过。

### 旧链路仍保留的兼容范围

`academic`（学业成绩）、`language`（外语能力）、`honor`（荣誉称号）、
`certification`、`research`、`competition_evidence` 等尚未迁移类别。
以上仅说明旧接口仍保留部分兼容能力，不代表每个类别的新提交都只走Application。certification、research、competition_evidence也有统一材料人工核验入口；以实际前端路由与后端allowed_actions为准。旧入口**不得写入已迁移类别**。

## 二、依赖清单（物理删除前必须处理）

| 位置 | 依赖方式 | 物理删除 `application` 的后果 |
| --- | --- | --- |
| `material_models.py:11` | `MaterialRecord.application_id` 外键（可空） | 变成孤儿，外键开启后被拦 |
| `automation_models.py:28` | `AutomationBatch.application_id` 外键（唯一） | 志愿批次失去关联 |
| `certificate_models.py:9` | `CertificateAssessment.application_id`（模型与修复迁移为RESTRICT） | 迁移后的库阻止删除；未升级旧库仍可能CASCADE |
| `workflow_models.py:591` | `LegacyBackfillItem.application_id`（非空外键） | 直接删除失败 |
| `use_cases/scoring.py` | `adapt_legacy_application`，`source_type='legacy_application'` | 已生成分数失去来源解释 |
| `services/automation.py:397` | 读 `application.final_score` 计算志愿年度增量 | 志愿上限分配失效 |
| `blueprints/application_bp.py` | 135 处引用（列表、审核、统计、导出） | 大面积 500 |
| `frontend/src/stores/applications.js`、`pages/admin/applications/ApplicationManagement.vue`、`pages/student/applications/ApplicationHistory.vue` | 历史查询、编辑、删除 | 历史页不可用 |

**存量库必须真实升级才能消除旧CASCADE**。模型已为RESTRICT，ORM父删除级联也已移除；旧申请删除接口另有证据保护。2026-11-21仅在一致性备份副本完成约束升级演练，原开发库未升级，不能因代码变化就认定原库已被保护。仍禁止批量删除旧申请。

## 三、退出步骤（分三段，不要跳步）

### 阶段 1：堵住新写入（已完成）

- `POST /api/applications` 对已迁移类别返回 `409`，覆盖"带 `rule_id`"和"只带 `application_type`"两种请求；
- 历史查询保留；所有写入口须登录，创建/编辑绑定本人，审核限定同学院教师/管理员；
- 已通过/已驳回只读，仅pending可审核；已迁移类别禁止从旧PUT修改；
- 删除仅允许无识别、材料、批次、计分或审核证据的本人draft，提交失败保留原件；
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
  但已有数据库须完成真实迁移并核对PRAGMA foreign_key_check；模型声明和连接开关不代表旧外键已自动升级，20261121_certificate_restrict已支持历史未命名SQLite外键；副本演练通过不代表原库已升级；
- 测试环境通过 `SQLITE_FOREIGN_KEYS=0` 关闭外键，因为多个用例刻意构造孤儿数据验证容错路径；
  需要用外键跑整套回归时：`$env:SQLITE_FOREIGN_KEYS='1'; pytest`；
- WAL模式下不要直接复制正在运行的数据库文件；应使用SQLite一致性备份接口或经验证的停机备份流程。本轮提供只读源库的副本演练工具：`backend/tools/check_legacy_application_upgrade.py --source <源库>`。它拒绝覆盖已有副本，核对逐表摘要和外键，不更新Alembic版本号；生产升级仍应走正常迁移流程。


## 五、2026-11-21最小修复交付

实现和验证归属独立变更：`openspec/changes/secure-legacy-application-compatibility/`。低风险界面维护仍属于另一个变更。最终验证与尚未执行的数据库/浏览器验收见本变更的evidence.md。

本轮保留旧Application与所有历史宿主依赖，未实施阶段2业务迁移或阶段3物理删除。旧证书预览/确认/重试/审核仍是兼容链路；完整退出须另行排期。
