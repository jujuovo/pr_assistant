# 可审计计分与重算

## 统一审核计分用例

单条材料审核由 `use_cases.materials.review_material` 协调，HTTP Blueprint 只负责解析请求、鉴权上下文、调用用例和提交/回滚。测试和批量处理的每个材料原子单元也必须直接调用该用例，不得导入 Blueprint 函数或复制日期资格、规则匹配、自动分、人工改写和快照逻辑。

统一事务按以下顺序处理：来源版本 CAS → 核验结论 → 固定周期日期资格 → 唯一已发布规则 → 自动分/授权改写 → `ScoreEntry` 与改写审计 → 学生周期快照 → 旧字段兼容投影 → draft 排名失效 → 审核事件与幂等结果。任一步异常由入口回滚整个数据库事务；OCR、通知等非权威副作用不在该事务内决定审核或分数。

命令以 `source_type + source_id + source_version` 标识来源版本，以 `idempotency_key` 标识重试。相同键和相同摘要返回原结果，不重复写事实；相同键携带不同内容返回 `idempotency_conflict`。批量入口不得把多条材料合成一个不可分事务：每条材料分别使用来源版本和幂等键调用统一用例，单条失败不能伪装为整批成功。

稳定错误码包括：

| 错误码 | 含义 |
| --- | --- |
| `forbidden` | 操作者没有来源范围内的审核或改写权限 |
| `source_not_found` | 来源不存在或不可见 |
| `version_conflict` | 来源版本已变化，需要刷新后重试 |
| `idempotency_conflict` | 同一幂等键被用于不同请求内容 |
| `cycle_policy_missing` | 来源没有可追溯的固定周期政策 |
| `award_date_missing` | 日期资格无法判断，需要补正 |
| `needs_rule` | 没有唯一适用的已发布规则版本 |
| `ambiguous_rules` | 存在多条同范围候选规则，禁止任选第一条 |
| `override_reason_required` | 人工改写缺少理由 |
| `override_out_of_range` | 人工改写为负数或超过规则单项上限 |
| `snapshot_failed` | 快照重建失败，整个审核计分事务回滚 |

审核结果始终分别表达 `overall_status`、`verification_status`、`scoring_status` 和 `allowed_actions`。`needs_rule` 是已核验但计分未完成，`verified_not_eligible` 是真实性通过但日期不符合本周期，两者都不能用笼统“审核成功”或裸 0 分代替。

## 计分事实

材料核验通过不等于自动获得分数。只有存在适用的已发布 `RuleVersion` 时，审核事务才创建 `ScoreEntry`。每条明细保存来源修订、规则版本、原始分、系数调整分、规则内最高分结果和是否实际计入。没有适用规则时返回 `needs_rule`，不得默认记零。

固定示例：基础学业成绩90、权重80%，两条学术专长明细10分和8分、一条综合表现明细7分；学院分类上限分别为15分和5分。结果为：

- 学术专长原始合计18，实际计入15；
- 综合表现原始合计7，实际计入5；
- 综合成绩 `90 * 80% + 15 + 5 = 92`。

同一规则存在 `max_count` 时，先按有效分降序、再按条目标识稳定排序，超出的明细保留但标记 `max_count_exceeded`。同一证明事实重复出现时标记 `duplicate_fact`。

## 撤销与补正

材料撤销、补正、拒绝或复核改变结论时，不删除原 `ScoreEntry`，而是写入 `invalidated`、失效原因和时间，再重建学生快照。旧快照改为 `superseded`，新快照成为 `current`。任何相关 draft 排名必须标记 stale；已发布排名不被覆盖。

## 预览与重算

管理员调用 `POST /api/workflow/scores/recalculate`：

```json
{"year":2026,"faculty_id":1,"preview":true}
```

可选 `student_id`、`rule_version_id`。`preview:true` 只返回预计输入摘要和综合成绩，不写快照；正式重算重复执行相同输入时返回同一快照且 `created:false`。响应中的 `complete:false` 和 `errors` 表示存在失败对象，不能把部分结果当作完整成功。

## 查询解释

`GET /api/workflow/students/{student_id}/score?year=2026` 返回基础成绩、权重、分类原始/实际分、综合成绩、公式、规则版本、输入摘要、更新时间和每条计分明细。学生仅能看本人，同院教师/管理员按职责访问。

## 运维约束

- 重算前备份生产数据库，并先执行 preview 与历史对账。
- 规则版本发布后不可修改；新政策创建新版本。
- 不直接修改 `Student.comprehensive_score` 修复差异，应修复来源或规则后重算。
- SQLite 结果不能替代生产数据库的迁移、锁和并发验证。

