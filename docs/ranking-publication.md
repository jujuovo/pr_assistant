# 排名批次与发布操作

排名不是 `Student.major_ranking` 上的无上下文数字。每个 `RankingBatch` 固定年度、学院/专业范围、截止时间、规则版本、精度和输入摘要。

## 生命周期

```text
draft --输入变化--> stale --重新生成--> draft
draft --完整性校验--> frozen --管理员解冻纠错并填写理由--> correction_required
correction_required --修正权威来源--> 新的 draft
frozen --管理员发布--> published
published --说明理由--> withdrawn --输入修正--> 新的 draft 后继版本
```

- `draft`：动态试算，可以重新生成，不得标记为正式结果。
- `stale`：相关学生试算分发生变化，旧名次不可继续显示为当前结果。
- `frozen`：参与者、分数、范围和规则版本已经冻结，等待发布。
- `correction_required`：未发布冻结批次发现错误；原条目不可编辑，必须修正权威来源并生成新 draft。
- `published`：正式版本，不受后续试算重算影响。
- `withdrawn`：正式版本因明确理由撤回；原条目和发布记录保留。

冻结前必须确认：没有 stale 输入、不可排名学生、迁移对账差异或失败对象，且操作者为本学院管理员。排名采用固定精度竞赛排名，同分示例为 `1, 1, 3`。

## 查询与导出

`GET /api/workflow/rankings/{batch_id}` 返回状态、版本、范围、规则版本、生成/发布时间和授权可见条目。学生默认只看到本人位置；同院工作人员按职责访问名单。

`POST /api/workflow/rankings/{batch_id}/export` 必须提供 `purpose`。系统记录操作者、批次、条目数、用途和时间。导出不创建第二份权威排名。

## 命令契约与审计

`POST /api/workflow/rankings/generate` 以及 `POST /api/workflow/rankings/{batch_id}/commands/{action}` 的每次写操作都携带 `version`（生成除外）与 `idempotency_key`。状态命令包括 `freeze`、`request_correction`、`publish`、`withdraw`、`create_successor`。响应 DTO 必须定义 `scope`、`status`、`version`、`generated_at`、`updated_at`、`published_at`、`reason_code` 和 `allowed_actions`。

命令写入 `RankingCommand`，状态变化写入 `RankingStateEvent`；正式名单导出写入 `RankingExportAudit`。学生 DTO 只含本人 entry，教师为授权范围完整只读名单且没有管理 actions，管理员 DTO 才返回状态命令。

## 纠错与回滚

已发布结果绝不原地覆盖。发现审核错误时：撤回旧版本并写理由 → 修正材料/计分 → 生成新输入摘要 → 创建带 `predecessor_batch_id` 的后继 draft → 重新冻结与发布。技术回滚也不得绕过该流程。

