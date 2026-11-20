# 验证记录（2026-11-21，Windows）

## 分支

- 独立修复分支：`fix/browser-back-navigation-20261121`（基于 `origin/main` `35f66bf`）。
- 未创建 PR，等待用户手动验证。

## 自动化验证

| 检查 | 命令 | 结果 |
|---|---|---|
| 导航历史回归测试 | `node --test frontend/tests/navigation-history.test.mjs` | 3 passed |
| 前端 mounted | `npm --prefix frontend run test:mounted` | 80 passed, 1 skipped |
| 前端生产构建 | `npm --prefix frontend run build` | 成功（保留既有大包提示） |
| 本次 change 校验 | `openspec validate fix-browser-back-navigation --strict` | valid |
| 全部 Node 测试 | `node --test frontend/tests/*.test.mjs` | 60 passed, 1 failed（既有 main 失败，见下） |

## 覆盖行为

- 学生/教师/管理员侧边栏切换页面、个人信息、编辑申请等主动导航使用 `router.push`，浏览器后退保留上一个业务页。
- 学生分类进入材料页、材料页/竞赛页进入「我的材料」、我的材料编辑草稿使用 `push`。
- 登录成功使用 `router.replace`，登录页不留在角色端历史。
- 取消编辑清理 `editId`、注销、未登录重定向、显式返回评测项目继续使用 `replace`。
- 当前页面重复点击不新增历史记录。

## 既有失败（不属于本次修复）

`node --test frontend/tests/*.test.mjs` 的失败项是 `teacher-core-workbench.test.mjs`：它要求 `TeacherStudentSummary.vue` 包含 `key_facts`，而 `origin/main` 本身也没有该字段。该失败在修复前已存在，不是本分支引入。

## 手动验收

- 2026-11-21 用户确认：三角色站内页面切换后，浏览器后退回到上一个业务页；登录后后退不再回到登录页。未保留截图。
- 本次只改前端导航，未修改后端、数据库、权限或计分；未重新执行后端回归。
