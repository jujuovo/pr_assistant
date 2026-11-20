# Tasks

## 1. 角色布局导航

- [x] 1.1 将 `StudentLayout.vue`、`TeacherLayout.vue`、`AdminLayout.vue` 的侧边栏 `switchPage`、个人信息和编辑申请等主动导航改为 `router.push`，并跳过当前页重复点击；用 mounted/源码回归测试验证后退历史。
- [x] 1.2 更新学生分类进入材料页的 `openApplicationForm` 为 `push`；验证从评测项目进入材料页后浏览器后退回到评测项目。

## 2. 材料与竞赛页面导航

- [x] 2.1 将 `MaterialWorkflow.vue` 的「前往我的材料」、`StudentMaterialsHub.vue` 的「编辑草稿」、`CompetitionWorkflow.vue` 的「前往我的材料」改为 `push`。
- [x] 2.2 保留取消编辑清 `editId`、显式返回评测项目等页内清理为 `replace`，避免无意义历史。

## 3. 登录历史

- [x] 3.1 将 `Login.vue` 正常登录成功后的角色跳转从 `push` 改为 `replace`；验证登录后从首页后退不会回到登录页。

## 4. 测试与验证

- [x] 4.1 更新现有路由断言（更正/编辑等改为 `push`），新增导航历史回归测试；运行全部 mounted、Node 和生产构建。
- [x] 4.2 运行 `openspec validate fix-browser-back-navigation --strict`，确认 change 有效。
- [ ] 4.3 由用户手动验证三角色：从首页进入多个业务页后按浏览器后退，应逐步回到上一个业务页；登录后后退不应回到登录页。

## Workflow follow-up

- 用户测试通过后再决定是否创建独立 PR；本修复不并入文体活动 PR。
