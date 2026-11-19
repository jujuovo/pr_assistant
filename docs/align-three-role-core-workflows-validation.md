# 三角色核心工作流验证记录

验证日期：2026-11-10（Asia/Shanghai）

## 任务 8.5：应用测试与生产构建

| 范围 | 实际命令 | 结果 |
| --- | --- | --- |
| 定向回归 | `D:\InteractionDesign\Myprogram\.venv\Scripts\python.exe -m pytest backend/tests/test_competition_rule_package_model.py::test_competition_package_migration_upgrades_and_downgrades backend/tests/test_migration_reconciliation.py::test_reconciliation_matches_imported_detail_and_student_total backend/tests/test_workflow_data_model_docs.py backend/tests/test_workflow_module_boundaries.py -q --basetemp D:\InteractionDesign\Myprogram\.pytest_tmp_8_5_targeted` | 5 passed，1 warning，5.83s |
| 后端全量 | `D:\InteractionDesign\Myprogram\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp D:\InteractionDesign\Myprogram\.pytest_tmp_8_5_full` | 549 passed，3 skipped，173 warnings，201.65s |
| 前端单元/组件契约 | 在 `frontend` 执行 `node --test tests/*.test.mjs` | 54 passed，0 failed，0 skipped |
| 生产构建 | 在真实仓库路径 `D:\InteractionDesign\Myprogram\frontend` 执行 `npm run build` | 通过；146 modules transformed，11.86s |

从目录联接 `D:\jiaohusheji\frontend` 首次执行生产构建时，Vite 将真实入口解析为跨根相对路径并报 `fileName/name` 非法；从真实仓库路径重跑通过。构建仍报告主 JS chunk 大于 500 kB 的非阻塞警告。

后端的 3 个 skipped 测试未宣称通过；现有 SQLAlchemy legacy/deprecation 警告也未视为失败。仓库没有配置可执行的浏览器 E2E runner，因此本次未执行真实浏览器 E2E；关键三角色旅程由后端集成测试与前端 Node 组件/请求契约测试覆盖。

## 任务 8.6：PostgreSQL 16 上线门槛

验证环境为用户提供的隔离 Docker 数据库 `gradpush_openspec`，PostgreSQL 16.15。先执行当前 Alembic upgrade，再执行：

`D:\InteractionDesign\Myprogram\.venv\Scripts\python.exe backend/tools/validate_postgres_core_workflows.py`

验证运行 `3ed092b7` 的结果：

- 同周期/范围第二个 current 规则包被数据库唯一约束拒绝。
- 两个并发排名状态命令基于同一版本 CAS，仅一个更新成功；`SELECT ... FOR UPDATE` 的竞争连接在 `500ms` lock timeout 下被阻塞并失败。
- 对同一学院 2 名学生执行真实 `recalculate_score_snapshots` 批量重算，生成 2 个 current 快照。
- 排名状态更新后故意复用 `RankingCommand.idempotency_key` 触发异常，整个事务回滚，未留下部分状态。
- PostgreSQL 执行计划在禁用顺序扫描后分别命中 `ix_ranking_batch_workflow_scope`、`ix_score_entry_recalculation_scope` 和 `ix_score_snapshot_current_scope`；规则 current 使用 `uq_competition_package_current_scope`。

新增索引迁移后再次运行完整后端套件：549 passed，3 skipped，173 warnings，207.03s。

该环境证明当前 schema 在 PostgreSQL 16 目标方言上的约束、事务、锁和索引行为，不等同于真实生产数据、生产负载或生产部署验收。
