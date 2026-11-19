# 材料、计分与排名数据模型

本文说明统一工作流中的数据所有权。正式业务链为：材料事实 → 规则版本 → 计分事实 → 学生试算快照 → 排名批次。

## 权威来源与兼容投影

| 模型 | 所有权与权威字段 | 兼容说明 |
| --- | --- | --- |
| `MaterialRecord` | 材料归属、结构化申报、附件引用、核验状态和版本 | `verified` 不等于最终入分 |
| `MaterialEvent` | 创建、修改、提交、补正、核验和撤回的追加式历史 | 不用 `Application.review_comment` 代替历史 |
| `RuleVersion` | 已发布规则的不可变 `snapshot` 与 `digest` | 编辑 `Rule` 不改变历史版本 |
| `ScoreEntry` | 来源修订、`rule_version_id` 或 `competition_rule_package_id` 权威版本、候选/实际分、是否计入及失效原因 | `Application.final_score` 在兼容期是投影，不是新链路输入 |
| `CompetitionRulePackage` | 竞赛目录、矩阵、专项政策、内容摘要及 current/retired 生命周期 | 发布后不可原地修改；材料与分数保留历史包引用 |
| `CompetitionRulePackageRevision` | 可编辑草稿每次修订的不可变内容快照与摘要 | 正式包仍不可原地修改 |
| `CompetitionRulePackageCommand` | 规则包复制、编辑与发布命令的幂等账本 | 相同键与载荷重放不会重复写入 |
| `CompetitionNotificationIntent` | 规则更正后的可重试通知意图、尝试次数与发送结果 | 发送失败不回滚规则切换 |
| `StudentScoreSnapshot` | 某学生某年度可重建的当前试算结果与输入摘要 | `Student` 汇总字段在兼容期是只读投影 |
| `RankingBatch` | 排名范围、输入摘要、生命周期和发布/撤回审计 | `Student.major_ranking` 不是正式排名历史 |
| `RankingEntry` | 批次内冻结分、名次、展示顺序和资格结果 | 已发布条目不随试算重算覆盖 |
| `RankingCommand` | 排名生命周期命令的幂等键、请求摘要与结果 | 状态命令使用版本 CAS 并记录重放结果 |
| `ScoreRecalculationCommand` | 范围化批量重算的预览摘要、状态与逐对象结果 | 不以部分完成冒充整体成功 |
| `RankingExportAudit` | 正式或试算排名导出的操作者、用途、数量和时间 | 不保存第二份排名结果 |
| `RecommendationCyclePolicy` | 全局推免周期、奖状有效区间和不可变政策版本 | `SystemSettings.academic_year` 仅为兼容投影 |
| `ReviewScoringCommand` | 跨材料来源的审核计分幂等键、请求摘要、来源版本与结果 | `MaterialReviewCommand` 在兼容迁移期保留 |
| `ScoreOverrideAudit` | 自动分、改写分、差值、理由、操作者、来源及规则版本 | 追加式保存，不覆盖自动计算事实 |

## ORM 与迁移字段

以下清单由测试与当前 ORM 列集合对照；修改模型或迁移时必须同步更新。

- `RuleVersion`: `id`, `rule_id`, `version`, `status`, `snapshot`, `digest`, `match_terms_digest`, `match_schema_version`, `published_by`, `published_at`, `created_at`
- `ScoreEntry`: `id`, `student_id`, `faculty_id`, `year`, `cycle_policy_version_id`, `score_group`, `category`, `source_type`, `source_id`, `source_revision`, `material_record_id`, `rule_version_id`, `competition_rule_package_id`, `candidate_score`, `competition_work_group_key`, `competition_event_group_key`, `exclusion_stage`, `exclusion_basis`, `raw_score`, `adjusted_score`, `effective_score`, `included`, `exclusion_reason`, `status`, `invalidated_reason`, `invalidated_at`, `idempotency_key`, `created_at`, `updated_at`
- `StudentScoreSnapshot`: `id`, `student_id`, `faculty_id`, `year`, `version`, `status`, `academic_base_score`, `academic_weight`, `specialty_raw_score`, `specialty_score`, `performance_raw_score`, `performance_score`, `comprehensive_score`, `input_digest`, `rule_version_ids`, `cycle_policy_version_ids`, `breakdown`, `created_at`, `updated_at`
- `RankingBatch`: `id`, `year`, `faculty_id`, `major_id`, `scope_type`, `scope_definition`, `cutoff_at`, `rule_version_ids`, `score_precision`, `status`, `version`, `input_digest`, `predecessor_batch_id`, `source_summary`, `stale_reason`, `correction_reason`, `correction_requested_by`, `correction_requested_at`, `created_by`, `frozen_by`, `frozen_at`, `published_by`, `published_at`, `withdrawn_by`, `withdrawn_at`, `withdrawal_reason`, `created_at`, `updated_at`
- `RankingEntry`: `id`, `batch_id`, `student_id`, `score_snapshot_id`, `frozen_score`, `rank`, `display_order`, `eligible`, `exclusion_reason`, `created_at`
- `RankingExportAudit`: `id`, `batch_id`, `actor_id`, `entry_count`, `purpose`, `created_at`
- `RecommendationCyclePolicy`: `id`, `cycle_code`, `version`, `display_name`, `eligible_award_start_date`, `eligible_award_end_date`, `boundary`, `digest`, `status`, `active_marker`, `created_by`, `activated_by`, `activated_at`, `retired_at`, `created_at`
- `ReviewScoringCommand`: `id`, `source_type`, `source_id`, `source_version`, `idempotency_key`, `request_digest`, `result`, `created_by`, `created_at`
- `ScoreOverrideAudit`: `id`, `score_entry_id`, `source_type`, `source_id`, `source_version`, `rule_version_id`, `automatic_score`, `override_score`, `difference`, `reason`, `actor_id`, `created_at`
- `CompetitionRulePackage`: `id`, `package_id`, `cycle_code`, `scope_key`, `version`, `draft_revision`, `status`, `snapshot`, `digest`, `current_scope_key`, `source_package_id`, `source_digest`, `source_summary`, `created_by`, `updated_by`, `published_by`, `published_at`, `retired_at`, `created_at`, `updated_at`
- `CompetitionRulePackageRevision`: `id`, `package_id`, `revision`, `snapshot`, `digest`, `created_by`, `created_at`
- `CompetitionRulePackageCommand`: `id`, `command_type`, `idempotency_key`, `request_digest`, `package_id`, `result`, `created_by`, `created_at`
- `RankingCommand`: `id`, `idempotency_key`, `action`, `request_digest`, `batch_id`, `result`, `created_by`, `created_at`
- `ScoreRecalculationCommand`: `id`, `idempotency_key`, `request_digest`, `preview_digest`, `scope`, `status`, `result`, `created_by`, `created_at`

迁移顺序：

1. `20261104_rule_version.py`
2. `20261104_score_entry.py`
3. `20261104_score_snapshot.py`
4. `20261104_ranking_models.py`
5. `20261104_review_command.py`
6. `20261104_snapshot_caps.py`
7. `20261104_ranking_export_audit.py`
8. `20261105_cycle_policy.py`
9. `20261105_review_scoring_command.py`
10. `20261105_score_override_audit.py`
11. `20261109_competition_rule_package.py`
12. `20261110_rule_package_drafts.py`
13. `20261110_rule_package_commands.py`
14. `20261110_rule_package_revisions.py`
15. `20261110_ranking_correction.py`
16. `20261110_ranking_commands.py`
17. `20261110_ranking_source_summary.py`
18. `20261110_score_recalculation_commands.py`
19. `20261110_workflow_query_indexes.py`

## 写入规则

- Blueprint 只能调用应用用例，不得直接拼装审核、计分和排名副作用。
- 核心审核事务同时写入核验事件、计分事实、学生试算快照和排名失效标记。
- OCR 和通知在提交后独立执行，失败不修改权威核验状态。
- 历史 `Application` 只能经唯一兼容适配器转换为 `ScoreEntry`，重复执行不得重复入分。
- 在旧消费者、历史对账和回滚演练完成前，不得删除旧表或兼容字段。

