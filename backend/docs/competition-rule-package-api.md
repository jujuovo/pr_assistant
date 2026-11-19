# 竞赛规则包管理 API

正式竞赛政策以 `CompetitionRulePackage` 为唯一权威来源。`/api/rules` 是非竞赛兼容端点；存在正式竞赛包时，它拒绝创建、修改、删除或启停 `sub_type=competition` 的规则。

| 方法 | 路径 | 权限与语义 |
| --- | --- | --- |
| GET | `/api/competition-rule-packages` | 管理员查看历史、current 和 draft、来源链、revision 与审计时间 |
| POST | `/api/competition-rule-packages/copy` | 使用 `source_package_id`、`target_cycle`、`idempotency_key` 深复制已发布包 |
| PUT | `/api/competition-rule-packages/{id}/draft` | 使用 `draft_revision` CAS 保存完整草稿快照 |
| GET | `/api/competition-rule-packages/{id}/diff` | 只读返回结构化差异和材料影响 |
| POST | `/api/competition-rule-packages/{id}/publish` | 使用 `draft_revision` 与 `idempotency_key` 完整校验并原子发布 |

每次复制、发布命令写入 `CompetitionRulePackageCommand`；每次草稿保存写入不可变 `CompetitionRulePackageRevision`。已发布包不可原地修改或删除。正式发布失败不留下 current 切换、命令审计或部分 revision。
