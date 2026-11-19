# 三角色核心工作流现状清单

本清单是 `align-three-role-core-workflows` 的实施基线。页面名称是角色 Layout 内的页面键；顶层路由仅有 `/student`、`/teacher`、`/admin`。`MaterialRecord`、不可变规则版本、`ScoreEntry`/计分快照和排名批次是新链路的权威来源；`Application` 与可变 `Rule` 仅用于尚未迁移的非竞赛兼容链路。

## 学生

| 页面/入口 | API / service | 权威来源 | 允许动作 | 兼容状态 |
| --- | --- | --- | --- | --- |
| `materials` → `CompetitionWorkflow.vue` | `materialApi`: `/api/materials/competition/**` | `MaterialRecord` + 当前 `CompetitionRulePackage` + 后端候选/计入分 | 保存材料事实、上传附件、OCR 辅助、提交、修正、重新确认、放弃 | **新链路**；请求禁止规则选择和分数字段，不得创建 `Application` |
| `materials` → `MaterialWorkflow.vue`（其他结构化类别） | `materialApi`: `/api/materials/<category>/records` | `MaterialRecord` | 按后端版本和状态执行材料动作 | 渐进迁移；不得回落到竞赛旧接口 |
| `application` → `ApplicationForm.vue` | `api.getRules/calculateRuleScore/createApplication` | `Application` + 可变 `Rule` | 未迁移类别的旧申报与估算 | **compatibility only**；竞赛必须分流到 `CompetitionWorkflow` |
| `history` → `ApplicationHistory.vue` | `/api/applications`, `/api/rules` | `Application` | 查看旧申请历史 | **compatibility only**；不作为竞赛计分来源 |
| `statistics` → `Statistics.vue` | `/api/students/statistics` + `materialApi.reconfirmSubmit` | 当前混合展示，目标为权威 `StudentScoreSnapshot` | 只读查看、对待重新确认材料发起明确动作 | 待迁移；不得直接写综合分或排名 |
| `rankings` → `RankingBatch.vue` | `workflowApi.getRanking/exportRanking` | `RankingBatch` + `RankingEntry` | 学生最终仅查看本人获准字段 | 待按角色裁剪；不得返回他人 entries 或导出完整名单 |

## 教师

| 页面/入口 | API / service | 权威来源 | 允许动作 | 兼容状态 |
| --- | --- | --- | --- | --- |
| `TeacherCompetitionReview.vue` | `materialApi.listRecords/getCompetitionReviewContext/reviewCompetition/getTeacherCompetitionSummary` | `MaterialRecord` + 固定规则依据 + 后端候选分 | 查看原件和词条；按 `allowed_actions` 通过/退回并填写意见 | **新链路**；不允许选规则、覆盖分数或调用 `/rules` |
| `pending-review` → `PendingReview.vue` | applications store、`/api/applications/pending`、`/api/rules` | `Application` + 可变 `Rule` | 未迁移类别审核 | **compatibility only**；竞赛记录应进入专用审核页 |
| `review-history` → `ReviewHistory.vue` | applications store、`/api/applications`、`/api/rules` | `Application` | 查看/处理未迁移类别历史 | **compatibility only**；不得更新竞赛 `MaterialRecord` |
| `statistics-report` | 统计查询 | 后端汇总结果 | 授权组织范围只读 | 待统一到 presentation DTO |
| `rankings` → `RankingBatch.vue` | `workflowApi.getRanking/exportRanking` | `RankingBatch` + `RankingEntry` | 授权范围完整名单只读 | 待按角色裁剪；不得生成、冻结、发布、撤回或编辑 |

## 管理员

| 页面/入口 | API / service | 权威来源 | 允许动作 | 兼容状态 |
| --- | --- | --- | --- | --- |
| `rule-management` → `RuleManagement.vue` | `/api/rules/**`、`structuredRuleApi` | 可变 `Rule` / 结构化规则草稿 | 仅管理未迁移类别；竞赛正式包必须由规则包命令管理 | **compatibility only**；不得修改、删除或逐条启停已发布竞赛包 |
| `score-management` → `ScoreManagement.vue` | `/api/students/**`、旧批量重算 | 学生基础资料与旧派生列 | 目标仅编辑权威基础资料；派生结果只读；重算走受控命令 | 待迁移；不得提交综合分、分类汇总、专业名次或人数 |
| `rankings` → `RankingBatch.vue` | `workflowApi.getRanking/exportRanking` | `RankingBatch` + `RankingEntry` | 目标为生成、冻结、纠错、发布、撤回、后继版本等单事务命令 | 待补齐；不得直接编辑 `RankingEntry` |
| `data-management` → `ApplicationManagement.vue` | `/api/applications`、`/api/rules` | `Application` | 管理未迁移类别申请 | **compatibility only**；不得作为竞赛材料或竞赛分数来源 |
| 组织、用户、文件、系统设置页 | `/api/admin/**` | 相应基础主数据 | 授权范围内管理基础数据 | 与竞赛计分链路无直接写入关系 |

## 交叉写入评审结论

- [x] 竞赛学生入口只调用 `/api/materials/competition/**`，请求由 `buildCompetitionFacts` 白名单装配，并拒绝 `rule_id`、`self_score`、`final_score`、`dynamic_coefficients`、`override_score`、`override_reason`。
- [x] 竞赛教师入口只通过 `reviewCompetition` 写入材料审核命令，不调用 `/api/rules`、`/api/applications` 或旧成绩更新接口。
- [x] 非竞赛旧入口保留 `Application`/`Rule`，但标记为 compatibility；它们不得接收 `competition` 类别写入，也不得生成竞赛 `ScoreEntry`。
- [x] 管理员旧规则、申请和成绩页目前仍是迁移风险点，后续任务必须先增加后端拒绝，再移除竞赛入口；在完成前不能把“隐藏按钮”视为权限控制。
- [x] 排名和计分快照只从后端权威模型读取；任何角色页面均不得通过资料更新请求写派生分数或名次。

自动化评审由 `backend/tests/test_role_workflow_inventory.py` 固化：验证清单覆盖三角色与两套权威模型，并检查竞赛前端没有引用旧 Application API，兼容表单没有导入竞赛材料 service。
