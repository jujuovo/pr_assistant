# Proposal

## Why

学生端「提交材料 → 文体活动」当前被路由到旧 `ApplicationForm`，旧表单会自动绑定当前唯一规则（学科竞赛），后端因此返回 `409 competition_material_route_required`，导致学生填写信息并上传原件后既不能保存草稿也不能提交。后端材料工作台也没有 `arts_sports` 类别，所以文体活动链路实际不可用。

## What Changes

- 新增手工材料类别 `arts_sports`（文体活动），复用 `MaterialRecord` 与既有手工材料用例 `submit_manual` / `review_manual`；不新增数据表、不做数据库迁移、不修改计分或排名规则。
- 保留原有五个提交项不变：文体竞赛、表演展示、文体表彰、文明宿舍表彰、体质健康测试。
- 学生端「文体活动」卡片改走材料工作台，与社会实践/志愿服务使用相同页面骨架：填写并上传 → 保存草稿 → 在「我的材料」正式提交。
- 教师端「其他材料人工核验」类别增加「文体活动」，教师可查看原件和学生申报值，并执行核验通过、退回补充、核验不通过。
- 学生主页「非竞赛材料审核进度」同时汇总旧兼容申请与新材料记录，使已核验通过的文体活动材料计入「已通过」份数；竞赛统计保持原样。
- 同步后端类别定义与校验、前端路由/表单/教师端/主页统计、OpenAPI、文档和测试。
- 范围外：不修改学业竞赛、学业成绩、志愿服务、社会实践、社会工作、学术创新、能力认证、目录外竞赛等现有类别；不修改旧 `ApplicationForm` 的其他兼容路径；不新增文体活动计分规则；不修改权限、排名或 OCR 行为。

## Capabilities

### New Capabilities

无。本变更复用既有手工材料能力，不新增 capability。

### Modified Capabilities

- `material-evidence-review`: 增加文体活动手工材料类别的草稿保存、正式提交、教师核验/退回、范围保护和版本冲突要求。

## Impact

- 后端：`backend/services/materials/ocr_schemas.py`、`backend/services/materials/schemas.py`、`backend/use_cases/manual_materials.py`（新增类别与校验）、`backend/docs/openapi-materials.json`。
- 前端：`frontend/src/services/materialWorkflowRoutes.js`、`materialApi.js`、`MaterialWorkflow.vue`、`ManualMaterialDraft.vue`、`MaterialFieldsEditor.vue`、`ManualMaterialReview.vue`、`StudentMaterialsHub.vue`、`materialFields.js`、`pages/student/home/Home.vue`。
- 测试：新增 `backend/tests/test_arts_sports_material.py`、`frontend/tests/arts-sports-material.mounted.test.js`、`frontend/tests/student-home-count.mounted.test.js`；更新现有类别集合断言与 OpenAPI 示例测试。
- 数据与兼容：`MaterialRecord.category` 为字符串，无需迁移；当前开发库不存在文体活动旧 `Application` 记录。若其他环境存在旧记录，保留在「历史兼容记录」只读展示，不迁移、不删除、不转换为新材料。
- 角色：学生、教师；管理员规则/排名流程不改变。
