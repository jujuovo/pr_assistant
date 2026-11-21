# Proposal

## Why

站内页面切换普遍使用 `router.replace`，浏览器历史只保留登录页和当前业务页；登录成功又使用 `router.push`，把登录页留在历史中。因此用户在任意业务页按浏览器后退键会直接返回登录大屏，而不是上一个操作页。

## What Changes

- 学生、教师、管理员布局的侧边栏页面切换、分类进入材料页、个人信息、编辑申请等主动导航改用 `router.push`。
- 材料页/竞赛页进入「我的材料」、我的材料「编辑草稿」等主动导航改用 `router.push`。
- 登录成功后改用 `router.replace`，移除登录页历史记录。
- 保留 `router.replace` 用于页内参数清理、注销、未登录重定向和显式逻辑返回，避免产生无意义历史。
- 当前页面重复点击时不新增重复历史记录。
- 不修改页面内容、接口、权限、计分、审核或数据模型。

## Capabilities

### New Capabilities

- `browser-navigation-history`: 定义三角色站内页面导航如何写入浏览器历史，以及后退键的预期行为。

### Modified Capabilities

无。本次只修复浏览器历史行为，不改变业务规格。

## Impact

- 前端：`StudentLayout.vue`、`TeacherLayout.vue`、`AdminLayout.vue`、`MaterialWorkflow.vue`、`StudentMaterialsHub.vue`、`CompetitionWorkflow.vue`、`Login.vue`。
- 测试：导航历史回归测试、现有路由调用断言更新。
- 后端、数据库、部署和权限：无变化。
