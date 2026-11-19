# 2028 届竞赛闭环验证记录

验证日期：2026-11-10（Asia/Shanghai）。本记录只声明下列实际执行环境；用户提供的 PostgreSQL 是隔离的生产方言验证库，不冒充真实线上业务库。

## 关键旅程

- 学生：正式目录与 field schema → OCR 等待/取消/手填 → 团队字段 → 附件 → 提交 → 本人反馈。
- 教师：同院权限 → 原件/OCR/确认值/固定规则/候选分只读上下文 → `approve` 或 `return` → 原子计分或补正。
- 规则更正：只读影响预览 → 新包原子切换 → 旧分失效 → 通知重试 → 学生新版本重新确认 → 教师重新审核。
- 计分政策：国家/省级矩阵、团队系数、CSP、同年 ICPC/CCPC、同赛事、同作品、最高三项及 15 分封顶由领域表驱动与聚合测试覆盖。
- 并发与失败：审核幂等重放、异载荷冲突、旧版本拒绝、OCR 迟到隔离、规则切换四阶段故障注入、审核三阶段故障注入均覆盖。

## 实际命令与结果

- `python -m pytest backend/tests -q --basetemp=.pytest_tmp_competition_full2`
  - 结果：`509 passed, 3 skipped, 0 failed`。
  - 跳过项由测试自身的平台/可选环境条件控制；未将其宣称为已执行验证。
- `node --test tests/*.test.mjs`（`frontend` 工作目录）
  - 结果：`25 passed, 0 failed`。
- `npm run build`（真实仓库 `frontend` 路径）
  - 结果：Vite 生产构建成功，137 个模块；主 bundle 有超过 500 kB 的性能警告，不影响构建成功。
- PostgreSQL 16：`gradpush-openspec-pg` / `gradpush_openspec`
  - revision 从 `20261109_competition_evidence` 升到 `20261109_competition_notify`。
  - 新 migration 成功 downgrade 至 evidence 后再 upgrade。
  - 验证 `ck_score_entry_rule_authority`、通知状态/重试约束、同 scope 唯一 current 及竞赛复合索引存在。
  - 两连接 `SELECT ... FOR UPDATE` 验证第二连接在 `lock_timeout=500ms` 下正确超时。
  - 单事务修改材料并写通知后 `ROLLBACK`，材料恢复 `submitted/version=1` 且通知数为 0。
  - 对账结果：旧竞赛有效来源 0、新竞赛有效来源 0、双计分连接结果 0（隔离库无业务数据，因此只证明查询与零基线，不代表真实线上存量对账）。
  - 锁测试使用 `OPENLOCK`/`openspec-lock-*` 临时数据，验证后计数为 0，已清理。

## 三角色与范围确认

- 学生反馈 API 从登录学生身份取 `student_id`，不接受目标学生参数；教师身份调用被拒绝。
- 教师只可审核同院材料、读取同院学生汇总，竞赛写命令不接受事实、规则或分数覆盖字段。
- 管理员负责受保护的正式包初始化/更正；管理员不能冒充教师执行竞赛审核。
- 本 change 未增加 2029 规则复制编辑 UI，也未改变既有排名冻结/发布职责；分数变化只使 draft 排名失效。
- 非竞赛旧 `Application`/`Rule` 路径仍保留，竞赛新提交禁止创建旧计分来源。

## 已知非阻塞事项

- SQLAlchemy 在部分既有 flush 路径输出 attribute-history 警告；完整测试仍通过，但应作为后续技术债清理。
- 前端主 bundle 超过 Vite 默认 500 kB 告警阈值，可在独立性能优化 change 中代码分割。
