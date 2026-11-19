# 2028 竞赛规则包初始化与运行手册

## 安全初始化

1. 先执行数据库备份，并保存为非空的绝对路径文件。
2. 不带 `--execute` 运行 `backend/tools/init_competition_2028.py`，审阅预计删除数量。
3. 仅在已确认现存竞赛数据均为测试数据时设置 `COMPETITION_RESET_ALLOWED=YES`。
4. 使用 `--execute --confirm RESET-COMPETITION-2028` 执行；工具拒绝缺失备份、错误确认词或未授权环境。
5. 重跑必须返回同一 current 包，且数据库内只能存在一个 `cycle_code=2028, scope_key=global, status=current` 的规则包。

清理范围仅包括竞赛 OCR 任务、竞赛材料事件/附件、竞赛 `ScoreEntry`、竞赛 `MaterialRecord`、可明确关联竞赛规则的旧 `Application` 以及竞赛规则包。其他材料类别和身份、组织数据不在范围内。

## 迁移与回滚

先在隔离数据库执行升级、约束检查、降级和再次升级。SQLite 结果不得替代 PostgreSQL 结论。回滚竞赛入口时关闭功能标志并导出新链路审计数据，不得把新数据反投影为旧 `Application` 正式分。

## 双计分监控

竞赛材料必须满足：`application_id IS NULL`、绑定一个竞赛规则包、审核后至多一个当前有效竞赛计分来源。任何竞赛旧 `Application` 有效分或同来源多条有效 `ScoreEntry` 都属于发布阻断项。
