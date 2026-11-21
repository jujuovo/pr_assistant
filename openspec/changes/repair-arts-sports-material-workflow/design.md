# Design

## Context

现有材料工作台已经为 `social_practice`、`research`、`certification`、`competition_evidence` 等手工类别提供完整的 `MaterialRecord` 生命周期。`backend/use_cases/manual_materials.py` 的 `is_manual`、`submit_manual`、`review_manual` 明确区分手工材料与自动计分材料；`backend/services/materials/service.py` 在 `is_manual(row)` 时允许教师读取已提交材料，不要求固定规则版本。

学生端 `ApplicationCategories` 已有 `arts-sports` 卡片，但 `materialWorkflowRoutes` 没有映射，`submissionQuery` 因此回退到旧 `ApplicationForm`。旧表单会为文体活动绑定当前唯一规则（学科竞赛），后端返回 `409 competition_material_route_required`。同时材料类别注册表没有 `arts_sports`，直接改路由也会 404。详见 `proposal.md`。

## Goals / Non-Goals

**Goals:**

- 用现有手工材料用例打通文体活动的草稿、提交、我的材料、教师核验/退回链路。
- 保留原有五个提交项和旧表单已收集的字段：提交项、项目名称、获得时间、原件。
- 让新材料类别只影响文体活动，其他类别和旧 `Application` 兼容路径行为不变。

**Non-Goals:**

- 不新增文体活动计分规则或 `ScoreEntry` 生成逻辑。
- 不把文体活动迁移到 OCR 或自动规则匹配。
- 不重构 `Application`/`MaterialRecord` 的长期收敛，不删除旧兼容入口。
- 不改变教师工作台、排名、权限系统的整体结构。

## Decisions

### 1. 新增 `arts_sports` 手工材料类别，复用 `MaterialRecord`

在 `backend/services/materials/schemas.py` 的 `TYPES` 中直接注册类别，并把它加入 `backend/services/materials/ocr_schemas.py` 的 `MANUAL_TYPES`。这样：

- `category_exists`、`type_view`、`create_manual_with_files` 自动接受该类别；
- `is_manual(row)` 为真，提交走 `submit_manual`，教师读取走手工材料豁免分支；
- `normalize` 只需要新增字段校验，不需要新表或迁移。

替代方案是把类别放进 `NEW_TYPES`，但 `OCR_CATEGORIES` 由 `NEW_TYPES` 推导，会把文体活动误标为 OCR 可用。选择直接注册 `TYPES` 并单独维护 `ARTS_SPORTS_TYPES` 常量。

### 2. 五个提交项作为 `document_type` 枚举保存

类别字段为 `document_type`、`project_name`、`award_date`、`reference_id`，必填前三项。`document_type` 只接受：

- `arts_competition` 文体竞赛
- `performance` 表演展示
- `arts_honor` 文体表彰
- `dorm_honor` 文明宿舍表彰
- `fitness_test` 体质健康测试

不按提交项拆成五个材料类别，避免教师端类别下拉和统计维度膨胀；也不动态增加每类专属字段，保持与旧表单“项目名称 + 获得时间 + 原件”的输入范围一致。

### 3. 类别规格通过 `type_view` 暴露提交项，前端不硬编码

后端在类别 spec 中返回 `document_types`，`ManualMaterialDraft` 把它传给 `MaterialFieldsEditor`；编辑器仅对 `document_type` 使用传入选项，其他类别保持原行为。这样提交项枚举只有后端一份权威定义，前端不能自行增加或改写。

替代方案是在前端维护 `arts_sports` 常量；会与后端校验产生漂移，且现有 `MaterialFieldsEditor` 的 `document_type` 选项本来就是硬编码的，容易误用其他类别的选项。

### 4. 复用现有 API 与教师组件，不新增接口

- 学生：`POST /api/materials/arts_sports/records`（multipart）保存草稿；`PATCH` 编辑；`POST .../submit` 提交。
- 教师：`GET /api/materials/arts_sports/records?reviewed=0` 列表；`POST .../review` 核验。
- 教师端 `ManualMaterialReview` 增加类别选项，`PendingReview`/`ReviewHistory` 已嵌入该组件，无需新页面。

状态转换沿用 `domain/materials.TRANSITIONS`：`draft → submitted → verified | needs_correction | rejected`，`needs_correction → draft` 后可重新提交。所有写操作使用 `_cas_change` 的版本校验；`submit_manual` 在同一事务内校验原件摘要并写事件，`review_manual` 在同一事务内写状态和审计事件。

### 5. 旧 `ApplicationForm` 保持原样，只改入口

`ApplicationForm.vue` 中 `arts-sports` 的旧配置不删除，避免影响其他旧类别或历史兼容；只是 `materialWorkflowRoutes` 不再把文体活动送到该表单。现有开发库没有文体活动旧 `Application` 记录；其他环境若存在，继续由历史兼容视图只读展示。

### 6. 学生主页新增非竞赛新材料统计聚合

新增 `GET /api/materials/student/summary`，只统计当前学生本人、非竞赛、`application_id IS NULL` 且未放弃的 `MaterialRecord`。返回 `status_counts`、`pending_count`、`approved_count`、`needs_correction_count`、`rejected_count` 和 `submitted_count`。主页把该结果与旧 `Application` 兼容申请按状态相加；`application_id` 非空的材料不计入，避免和旧申请重复。竞赛材料仍由既有 `competition/workbench-summary` 单独统计，不进入该接口。

这样既能让已核验通过的文体活动材料出现在主页「已通过」，又不改变旧兼容申请、竞赛统计或其他页面。新增接口是只读聚合，不写业务事实；权限只允许学生本人。

### 7. 教师主页新增本学院非竞赛待审聚合

新增 `GET /api/materials/teacher/summary`，只统计当前教师/管理员所属学院、`MANUAL_TYPES ∪ {volunteer, student_work}`、`application_id IS NULL` 且状态为 `submitted` 或 `under_review` 的 `MaterialRecord`。主页把该 `pending_count` 与旧兼容申请待审数相加，竞赛待审数继续来自 `competition/workbench-summary`。这样文体活动等新材料提交后会出现在教师主页，同时不改变旧兼容申请与竞赛统计。

### 8. 教师手工核验默认汇总全部类别

`ManualMaterialReview` 的类别选择增加 `all`（全部类别）并设为默认。`load()` 在全部视图下并发读取所有可核验类别，使用 `Promise.allSettled` 合并成功结果、按优先级排序并过滤状态；单类别视图只读取该类别。核验和历史事件使用每条材料的 `row.category`，不使用当前下拉值，避免在全部视图中把材料提交到错误类别。单类别失败不阻塞其他类别，页面显示可重试提示。

## Risks / Trade-offs

- [前端类别列表/OpenAPI 枚举存在多处精确断言] → 同步更新 `test_material_interfaces.py`、OpenAPI 示例和前端 `MATERIAL_CATEGORIES`，否则测试会明确失败。
- [编辑模式没有类别 spec 时会显示错误提交项] → `MaterialWorkflow` 编辑模式加载 `getTypes()` 并传入 `document_types`，新增 mounted 测试覆盖。
- [文体活动不计分，可能与用户预期不同] → 规格明确本类别只做人工核验；如后续需要计分，另立规则/计分变更，不在本次暗中扩展。
- [旧 `ApplicationForm` 的文体活动配置残留，可能被误用] → 入口路由已移除；保留代码仅用于兼容，后续单独清理。
- [教师默认类别是社会实践，可能找不到文体活动] → `ManualMaterialReview` 类别下拉增加文体活动并保持现有选择行为；浏览器验收覆盖教师切换类别。
- [主页旧申请与新材料重复计数] → 新材料统计只包含 `application_id IS NULL` 的记录，旧关联材料留在旧申请统计；新增后端测试覆盖该边界。
- [主页统计接口失败导致旧兼容份数也不可见] → 新材料统计失败时保留旧兼容计数，只在面板内显示可重试提示，不阻塞旧数据。

## Migration Plan

- 无数据库迁移：`MaterialRecord.category` 为 `String(32)`，`arts_sports` 可直接写入。
- 部署只需发布后端类别定义、前端路由/表单/教师端和 OpenAPI/文档。
- 回滚：回退本次提交并恢复 `backup-pre-arts-sports-20261120` 标签对应版本；已创建的文体活动材料记录在回滚后不会被删除，但入口会消失，需保留数据待后续处理。
- 上线前检查目标环境是否存在旧文体活动 `Application` 记录；存在时保留只读兼容，不做转换。

## Open Questions

无。计分范围已按“只人工核验、不自动计分”确定；如产品后续要求计分，另立变更。
