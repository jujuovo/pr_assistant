# 统一材料—计分—排名切换与回滚手册

## SQLite 变更迁移演练（2026-11-04）

在隔离文件数据库中以 `20261013_materials` 为变更前基线，顺序升级至
`20261104_backfill`，再完整降级回基线；八个 revision 的 upgrade/downgrade 均通过。
历史适配、回填、对账由专项测试验证：批次可续跑、失败隔离、来源幂等、逐明细/学生/排名差异稳定。
项目更早的 2025 年空库迁移链仍依赖部署基线，不能把本演练解释为空库全历史重建。

### 计分闭环增量复演（2026-11-06）

以部署基线后的 `20261105_score_override` 结构为前提，在独立 SQLite 文件中对
`20261106_backfill_evidence` 执行 upgrade、downgrade、再次 upgrade，新增的
`cycle_policy_version_id` 与 `evidence_manifest` 两列及外键均按预期出现、移除和恢复。
业务门禁测试共 `12 passed`：两条历史申请修复后得到 2 条唯一计分事实、1 个当前快照、
1 个修复批次和 2 个对象记录；中断续跑与重复执行没有重复入分，单对象失败不影响其他对象，
dry-run 两次摘要一致，无法证明周期的对象进入 1 条人工清单/发布阻塞记录，旧读取投影仍保留。

同时实际尝试了从空库执行全历史 upgrade；历史 revision `f7bee6350526` 因初始 revision
未创建 `rule` 表而失败。该失败发生在本 change 之前，故生产迁移必须从已验证部署基线/备份
恢复副本开始，禁止把“空库全历史重建”列为已通过能力。

### 结构化词条与规则闭环复演（2026-11-08）

在隔离 SQLite 测试数据库运行新增材料规则绑定、结构化规则、结构化词条和结构化历史迁移，
并复演规则交集/唯一匹配、发布覆盖扫描、学生再确认、日期补正和审核事务回滚，共
`22 passed`。迁移升级/降级保留旧材料与审核数据；无规则对象只进入 `rule_unmatched`，发布
唯一规则后只进入 `rule_available`，未产生教师审核、`ScoreEntry` 或伪造快照。迁移批次仅
使用已有学生确认事实，OCR-only 对象进入补正清单且不直接补分。

SQLite 只证明结构和业务行为，不证明真实行锁与 PostgreSQL 并发语义。本次没有运行真实 OCR，
因此以上结论不包含 OCR 识别准确率或模型可用性。

## PostgreSQL 生产类型演练（2026-11-05）

在隔离的 PostgreSQL 16.15 容器中，以 `20261013_materials` 为变更前基线执行八个
revision 的升级、完整降级和再次升级，全部通过。`tools/validate_postgres_workflow.py`
确认迁移表存在、`ScoreEntry` 重复来源/幂等唯一约束生效、两个并发审核 CAS 只有一个成功，
且第二个 `SELECT ... FOR UPDATE` 在 `500ms` 的 `lock_timeout` 下被正确阻塞。

与 SQLite 的差异：PostgreSQL 使用 transactional DDL，并提供真实行级锁和锁超时；SQLite
演练只能覆盖结构与业务结果，不能替代并发锁结论。生产切换仍须使用与目标生产主版本一致的
隔离实例复跑本脚本，不得复用本次临时测试凭据。

### 计分闭环 PostgreSQL 复演（2026-11-06）

在用户提供的隔离 PostgreSQL `16.15` 实例上，从实际 head `20261105_score_override`
升级到 `20261106_backfill_evidence`，随后 downgrade 回旧 head 并再次 upgrade；三步均成功，
最终 Alembic head 与新增两列核对一致。`validate_postgres_workflow.py` 实测迁移表、
`ScoreEntry` 唯一约束、并发审核 CAS 和真实行锁均为 `ok`。

`validate_postgres_backfill.py` 实测两条明确证据的历史申请：首轮只处理 1 条、续跑完成、
第三次重复运行后仍为 2 个对象记录、2 条 active 计分事实、1 个 current 快照，结果
`repair_resume=ok`。与 SQLite 相比，业务计数一致；PostgreSQL 额外验证了 transactional DDL、
唯一约束冲突和真实锁等待。以上结论仅适用于该隔离 PostgreSQL 16.15 实例。

### 结构化词条与规则闭环 PostgreSQL 复演（2026-11-08）

在隔离 `postgres:16-alpine` 实例（数据库端口仅绑定 `127.0.0.1`）上，从实际基线
`20261106_backfill_evidence` 升级至 `20261108_structured_migration`，降级回基线后再次升级，
最终 head 为 `20261108_structured_migration`。首次升级发现生产类型表
`alembic_version.version_num VARCHAR(32)` 无法保存过长 revision id；缩短两个新增 revision id
后，升级、降级和再次升级均通过。该故障已作为门禁经验保留：新增 revision id 必须适配目标
数据库现有版本列宽，不能只凭 SQLite 结果放行。

更新后的 `tools/validate_postgres_workflow.py` 实测结果为：`migration_tables=ok`、
`unique_constraint=ok`、`row_lock=ok`、`concurrent_resubmit_cas=ok`、
`concurrent_review_cas=ok`、`review_transaction_rollback=ok`。这证明了本隔离 PostgreSQL 16
实例上的迁移结构、唯一约束、真实行锁、并发再提交、并发审核和审核事务回滚；不代表未经
复演的生产实例或真实 OCR 已通过。

## 切换

1. 验证 PostgreSQL 备份可恢复，记录备份引用。
2. 在相同 PostgreSQL 主版本的隔离实例执行迁移、约束和并发审核测试。
3. dry-run 对账差异必须为零；否则禁止冻结和发布对应范围。
4. 运行历史回填，复跑对账至少两次。
5. 依次切换证书、志愿自动化、应用审核、新 API 与前端消费者。
6. 首次正式排名只从 `frozen` 批次发布。

## 监控指标与阻断条件

- `legacy_consumer_requests_total`：旧消费者未归零时不得删除兼容路径。
- `reconciliation_differences`：大于零时不得发布该范围。
- `score_recalculation_failures`、`review_conflicts`、`stale_ranking_batches`。
- 备份未验证、生产数据库迁移未验证、权限旅程失败，均阻断上线。

## 回滚

停止新入口写入后可把未发布读取切回旧接口，但保留新表和审计数据。已经发布的正式排名
不得由技术回滚覆盖；必须填写撤回理由，撤回原批次并创建后继版本。只有确认无新数据依赖且
备份可恢复时，才允许数据库降级。
