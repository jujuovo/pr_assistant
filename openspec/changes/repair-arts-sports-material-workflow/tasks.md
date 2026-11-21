# Tasks

## 1. 后端类别与字段契约

- [x] 1.1 在 `backend/services/materials/ocr_schemas.py` 定义五个文体活动提交项并加入 `MANUAL_TYPES`，在 `backend/services/materials/schemas.py` 注册 `arts_sports` 类别规格；用 `pytest backend/tests/test_arts_sports_material.py` 验证合法字段通过、非法提交项/短项目名/缺日期被拒绝。
- [x] 1.2 在 `backend/use_cases/manual_materials.py` 为 `arts_sports` 增加提交前至少一份原件的后端校验；用新测试验证无原件提交返回明确错误且材料保持草稿。
- [x] 1.3 更新 `backend/tests/test_material_interfaces.py` 的 `SAMPLES` 和类别集合断言，确认 `/api/materials/types` 与 OpenAPI 示例都包含 `arts_sports`；运行该测试文件通过。

## 2. 后端生命周期与教师核验

- [x] 2.1 新增 `backend/tests/test_arts_sports_material.py`，覆盖五个提交项的草稿创建、编辑、正式提交、学生列表可见和版本递增；运行该文件通过。
- [x] 2.2 在同一测试文件覆盖教师本学院列表、核验通过、退回补充、核验不通过、退回意见必填、外院教师 403、其他学生越权拒绝；运行该文件通过。
- [x] 2.3 验证文体活动核验通过不创建 `ScoreEntry`，并运行 `pytest backend/tests -q -p no:cacheprovider` 确认其他类别无回归。

## 3. 前端入口与学生表单

- [x] 3.1 在 `frontend/src/services/materialWorkflowRoutes.js` 增加 `arts-sports → arts_sports`，在 `frontend/src/services/materialApi.js` 的 `MATERIAL_CATEGORIES` 增加该类别；用 Node/mounted 测试验证 `submissionQuery('arts-sports')` 和 `recordsPath` 不再落到旧表单。
- [x] 3.2 修改 `MaterialWorkflow.vue`、`ManualMaterialDraft.vue`、`MaterialFieldsEditor.vue`，支持后端返回的 `document_types` 并覆盖编辑模式；用 mounted 测试验证五个提交项可见、保存调用 `createManualRecord('arts_sports', ...)`。
- [x] 3.3 在 `StudentMaterialsHub.vue` 增加文体活动名称；用 mounted 测试验证草稿卡片、正式提交按钮和 `materialApi.submit` 调用。

## 4. 教师端与文档

- [x] 4.1 在 `ManualMaterialReview.vue` 增加「文体活动」类别；用 mounted 测试验证教师列表、退回意见必填、核验调用 `materialApi.review('arts_sports', ...)`。
- [x] 4.2 更新 `docs/material-interfaces.md`、`docs/material-api-integration.md`、`backend/docs/openapi-materials.json`；运行相关 pytest 与 `openspec validate --specs --strict`。

## 5. 集成验证

- [x] 5.1 运行完整后端测试、mounted 测试、全部 Node 测试和前端生产构建，记录实际命令与结果。
- [x] 5.2 运行 `openspec validate repair-arts-sports-material-workflow --strict` 和 `openspec validate --changes --strict`，确认本次 change 通过；随后刷新 `openspec instructions apply`。
- [x] 5.3 检查 `git diff --stat` 与 `git status`，确认只改动本 change 范围内的文件，其他类别和旧兼容路径没有变化。

## 6. 学生主页非竞赛材料统计

- [x] 6.1 新增 `GET /api/materials/student/summary`，只统计当前学生本人、非竞赛、未关联旧申请且未放弃的 `MaterialRecord`；用 `pytest backend/tests/test_arts_sports_material.py` 验证已通过、审核中、待修改和排除竞赛/旧关联记录。
- [x] 6.2 修改 `frontend/src/pages/student/home/Home.vue` 与 `materialApi.js`，把新材料统计与旧兼容申请相加；用 `npm --prefix frontend run test:mounted -- tests/student-home-count.mounted.test.js` 验证已通过份数包含新材料且旧申请不重复。
- [x] 6.3 更新 OpenAPI 与文档，运行完整后端、mounted、Node 和构建，确认主页统计不改变竞赛统计、旧兼容申请或其他页面。

## 7. 教师主页非竞赛材料待审统计

- [x] 7.1 新增 `GET /api/materials/teacher/summary`，只统计本学院可审核的非竞赛新材料；用 `pytest backend/tests/test_arts_sports_material.py` 验证本学院、外院、学生拒绝和竞赛/旧关联排除。
- [x] 7.2 修改 `frontend/src/components/common/RoleHome.vue` 与 `materialApi.js`，把新材料待审数与旧兼容申请待审数相加；用 `npm --prefix frontend run test:mounted -- tests/teacher-home-count.mounted.test.js` 验证显示份数。
- [x] 7.3 更新 OpenAPI 与文档，运行完整后端、mounted、Node 和构建，确认竞赛统计、旧兼容申请和其他页面不变。

## 8. 教师手工核验全部类别

- [x] 8.1 在 `ManualMaterialReview.vue` 增加「全部类别」并设为默认，汇总所有可核验类别；用 mounted 测试验证默认同时显示多个类别，选择具体类别后只显示该类别。
- [x] 8.2 核验和查看历史事件改用每条材料的 `row.category`；更新现有教师核验测试并验证全部视图下的核验请求使用正确类别。
- [x] 8.3 运行完整 mounted、Node 和生产构建，确认单选类别、社会实践、志愿服务和文体活动核验行为不变。

## 9. 真实浏览器验收

- [ ] 9.1 由用户手动完成：学生保存文体活动草稿 → 我的材料正式提交 → 教师待审核中看到并退回补充 → 学生编辑重提 → 教师核验通过；同时确认主页「已通过」份数、教师主页「非竞赛材料待审核」份数和教师核验默认「全部类别」；记录路由、请求状态、截图和最终数据库状态，并明确标注未执行的生产数据库/其他浏览器检查。

## Workflow follow-up

- 所有任务和浏览器验收通过后，按仓库规则同步 `material-evidence-review` 主规格并归档本 change；归档前需用户明确批准。
- 如果后续要求文体活动计分，另立规则/计分变更，不在本 change 内扩展。
