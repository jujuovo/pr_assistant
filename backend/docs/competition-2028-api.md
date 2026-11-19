# 2028 届学业竞赛 API 契约

## 兼容边界

`competition` 是首个完成迁移的材料类别。新建、提交、审核和计分只能使用 `/api/materials/competition/*`，权威链为：

`MaterialRecord -> CompetitionRulePackage -> ScoreEntry -> StudentScoreSnapshot`

旧 `/api/applications` 若收到指向竞赛规则的请求，返回 `409 competition_material_route_required`，且不创建 `Application`。`academic`、`language`、`student_work`、`honor` 等尚未迁移类别继续使用既有兼容流程。

## 竞赛写入字段

竞赛写入只接受服务端目录标识、学生确认事实、材料版本和附件引用。服务端从绑定的正式规则包计算候选分及实际计入分。客户端不得选择规则、提交自评分或请求人工覆盖。

目录和字段模式由只读接口返回；创建材料后固定 `competition_rule_package_id`。提交时若当前包已变化，返回 `rule_package_changed`，不得自动换包或改分。

## 旧模型保留原因与退出条件

`Application`、`Rule`、`RuleCalculation` 和旧 `/rules` 暂不物理删除，因为未迁移类别仍依赖它们。满足以下条件后，才可由独立变更删除：

1. 所有材料类别均迁移到材料、规则快照和计分明细链路。
2. 生产环境连续完成新旧来源对账，确认不存在旧来源有效分。
3. 历史证据和审核记录完成导出/保留验证。
4. 删除迁移具备备份、回滚和生产数据库验证结果。
