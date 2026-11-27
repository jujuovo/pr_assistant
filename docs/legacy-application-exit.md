# 旧 Application 链路退出记录

> 结论先行：**新功能不要再和 `Application` 产生任何联系**。
> 旧链路保存的是「结果」（`self_score` / `final_score` + 一个指向可变 `Rule` 的指针），
> 保存不了「依据」；规则一旦修改，历史分数无法解释来源，因此**不可复算**，
> 这也正是它无法支撑自动计分的原因。

## 2026-11-25 退役结果

正式服务通过材料接口申报、识别和审核，通过 `ScoreEntry` 计分。新建库直接使用材料结构。旧的证书队列、申请表、两张历史回填表及材料和批次上的 `application_id` 列由迁移移除。历史模型集中在 `backend/legacy_models.py`，供离线旧库工具使用。

有版本号的数据库先备份，再在副本上使用现有 Flask-Migrate 的 `db upgrade` 入口。最新版本为 `20261125_retire_application`。没有版本号的本地 SQLite 开发库可用以下命令生成验收副本，目标文件必须是新路径。

```powershell
.\.venv\Scripts\python.exe -B backend/tools/rehearse_application_retirement.py backend/instance/gradpush-dev.db --output backend/outputs/retired-copy.db
```

演练按行核对保留表、附件元数据和计分，再检查完整性与外键。材料附件仍在原存储目录，更换部署目录时须一并备份原件。遇到未归档的旧申请、旧来源计分、旧关联或额外外键时，先核对提示中的数据。恢复此前版本时需要同时恢复旧程序和升级前备份。

以下记录描述 2026-11-21 的历史实现。

## 一、当时状态（2026-11-21）

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

## 六、旧批量志愿链路下线清单（2026-11-22 整理）

对象：`/api/automation/volunteer/**`（`backend/blueprints/automation_bp.py`，12 个路由）。
这套批量上传 + 政策分配的实现已被材料级志愿链路（`/api/materials/volunteer/records`）取代，
后者覆盖填报、OCR 比对、申诉、提交门禁、教师核定与年度累计封顶，且前后端均已接通。

### 现状核对

| 事实 | 数据 |
|---|---|
| 前端页面调用这些接口 | **0 处**（客户端 `frontend/src/services/volunteerApi.js` 已删除） |
| 后端测试引用 `/api/automation` | **46 处 / 6 个文件** |
| `services/automation.py` 被谁 import | **9 个模块**，其中 `actor()` 被 8 个后端蓝图共用 |

### 不能直接删的原因

`services/automation.py` 同时承载两件事：批量志愿业务 **和** 公共鉴权 `actor()`。
直接删除会连带打断 `application_bp`、`certificate_bp`、`material_bp`、`ocr_bp`、
`rule_bp`、`score_bp`、`workflow_bp` 与 `legacy_application_policy.py` 的正常工作。

### 下线步骤（需负责人确认后执行）

1. **抽出公共能力**：把 `actor()`（以及 `application_bp` 使用的 `authorize`）移到独立模块（如 `services/actors.py`），
   保持导入路径可控；`round_score` / `score_increment` 等志愿专用函数留在原处或随模块删除。
2. **确认无存量依赖**：`automation_batch` / `automation_item` / `automation_review` 三张表若已有数据，
   需先按阶段 2 迁移到 `MaterialRecord + ScoreEntry`，否则历史分数失去解释。
3. **删除路由与蓝图**：移除 `automation_bp` 的 12 个路由及 `app.py` 中的注册。
4. **同步改测试**：6 个文件 46 处引用需删除或改写；`test_automation_lifecycle.py` 中与"删除保护"相关的
   用例需移到旧申请删除保护的测试里，避免覆盖缺口。
5. **清理文档**：`docs/volunteer-automation.md`（532 行）应标注为已废弃或归档，
   否则后来者仍会照它去接前端。
6. **回归**：后端全量 + 前端挂载 + `node --test`，并确认教师端待审/汇总、学生端材料页不受影响。

### 风险提示

- 第 2 步是硬前置：库里只要还有按批次计分的志愿记录，删接口就会让"历史分数从哪来"无法解释。
- 这不是单方面可完成的改动，涉及 `services/automation.py` 拆分与 46 处测试改造，
  必须与模块负责人一起做。

### 执行结果（2026-11-23）

| 步骤 | 状态 |
|---|---|
| 1. 抽出公共能力 | ✅ 新增 `services/actors.py`；15 个模块改为从它导入 `actor()`。`services/automation.py` 保留同名再导出，旧调用方无需一次改完 |
| 2. 确认无存量依赖 | ✅ 实测本地库 `automation_batch/item/review/policy/fingerprint` 五张表均为 **0 行**，没有历史分数依赖批量链路 |
| 3. 删除路由与蓝图 | ✅ 删除 `blueprints/automation_bp.py`（10 个路由）与 `app.py` 中的注册；`app.url_map` 里已无 `/api/automation` |
| 4. 同步改测试 | ✅ 删除 5 个面向已下线接口的测试文件（`test_automation*.py`、`test_real_ocr.py`）；`test_automation_lifecycle.py` 重写为用 ORM 直接构造旧数据，保留"删除用户/学院/系/专业时的旧数据保护"5 组用例 |
| 5. 清理文档 | ✅ `docs/volunteer-automation.md` 已标注冻结，不得作为开发依据 |
| 6. 回归 | ✅ 后端 886 passed / 4 skipped；前端与 `node --test` 未受影响（本次未改前端） |

保留项：`services/automation.py` 的志愿业务函数仍在——`application_bp` 的旧申请审核路径
仍调用其中 `authorize` / `review_batch`。`automation_*` 模型与 `services/deletion.py`
的保护逻辑也保留，用于保护可能存在的历史数据。待阶段 2（旧申请迁到 `MaterialRecord`）
完成后可一并删除。
