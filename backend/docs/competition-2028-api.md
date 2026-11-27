# 2028 届学业竞赛 API 契约

## 兼容边界

`competition` 是首个完成迁移的材料类别。新建、提交、审核和计分只能使用 `/api/materials/competition/*`，权威链为：

`MaterialRecord -> CompetitionRulePackage -> ScoreEntry -> StudentScoreSnapshot`

正式服务已下线 `/api/applications`，竞赛材料从学生材料接口进入教师审核和计分。创建竞赛材料时，若客户端仍传入非空的 `application_id`，接口返回 `409 competition_material_route_required`。

## 竞赛写入字段

竞赛写入只接受服务端目录标识、学生确认事实、材料版本和附件引用。服务端从绑定的正式规则包计算候选分及实际计入分。客户端不得选择规则、提交自评分或请求人工覆盖。

目录和字段模式由只读接口返回；创建材料后固定 `competition_rule_package_id`。提交时若当前包已变化，返回 `rule_package_changed`，不得自动换包或改分。

## 数据库升级

旧申请表退出后的库结构、SQLite 副本验收命令和恢复方式见[旧申请链路退出记录](../../docs/legacy-application-exit.md)。竞赛规则包和材料计分版本继续保存审核依据。
