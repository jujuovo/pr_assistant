# 前后端计分链路验证（2026-11-23）

## 范围与复现

执行`.venv/Scripts/python.exe -B backend/tools/check_competition_score_flow.py`。默认创建唯一隔离目录，已有数据库不覆盖；原业务库不变。真实Flask HTTP + 生产前端API模块/表单校验/分数字段映射，共307个请求、36份材料、36个active计分事实，Application记录为0。

证据：backend/outputs/score-flow-20261123-180045/result.json；日志score-flow-acceptance-final.log。真实样本为backend/samples/LanqiaoCup/example5.jpg，使用本地PP-OCRv5模型。启动工具前须准备Node、Python依赖和backend/ocr-models。

## 蓝桥杯分值

| 获奖级别/奖项 | A-基准值 | 个人最终候选分 |
| --- | --- | --- |
| 国家级一等奖及以上 | 10 | 3.3333 |
| 国家级二等奖 | 5 | 1.6667 |
| 国家级三等奖 | 2 | 0.6667 |
| 省级一等奖及以上 | 1 | 0.3333 |
| 省级二等奖 | 0.5 | 0.1667 |

每种奖项均验证个人，以及2/3/4/6人团队（6人团队测试第5名）的既有系数；共25组。前端预估、保存事实、教师审核、ScoreEntry、学生统计前端映射、教师统计和教师正式报表保持一致。省级三等奖、6人团队第6名、伪造candidate_score均400。

## 累计、封顶与真实OCR

- 4份不同年度蓝桥杯材料：3.3333、1.6667、0.3333、0.1667，最终前三项合计5.3333，第四项保留候选分但计入0。
- 同作品国奖与省奖：只计较高3.3333，不重复累计。
- 三项不同A+个人国一：逐项合计30，学术组封顶15；学业基础76、权重80%，综合成绩75.8。不能直接把明细相加当总分。
- 学生工作：教师核定岗位和80分考核后计入综合表现1.2，学术专长0，综合成绩62.0。
- 真实OCR任务完成，报告为manual_review；识别证据不完整/与申报有差异时保留手填事实和0.1667候选分。审计快照中识别为三等奖、2026-05-08，学生申报为省级二等奖、2027-05-01；differences正确包含award和award_date，因缺level/scoring_basis/recognition_quality不提供OCR建议分（null）。未确认审核409，人工确认后审核200并正式计分。此测试证明差异门槛与链路，不证明样本申报真实或OCR对所有图片准确。

## 发现并修复

1. 前端旧类别映射遗漏student_work，可能把学生工作显示为学术专长。后端现从真实ScoreEntry附带score_group，前端优先采用它，并对旧student_work返回兼容归组。正式分值不变。
2. 后端已生成faculty_scoring_policy，但DTO过滤掉该字段，页面无法展示总规则依据。现保留该字段，并在真实链路断言存在。

## 常规回归和限制

后端完整回归899 passed、4 skipped（score-flow-full-backend-final.log）；前端挂载134 passed（score-flow-mounted-final.log），Node63 passed，生产构建通过。首次全量中旧精确字段集合测试未包含新增score_group，已同步契约并断言真实academic值，再次全量通过。保留既有SQLAlchemy/pytest告警，不宣称已修复。完整验收没有自动化浏览器，不覆盖登录验证码UI、部署中PostgreSQL或其他操作系统。本地真实业务库仍需前述迁移，不能把隔离库通过等同于日常运行库已更新。

浏览器手工验收建议：蓝桥杯省级一/二等奖能预估和保存；教师确认OCR差异后审核；学生统计与教师报表分值一致；学生工作显示综合表现；详情能看到总规则依据。相关浏览器任务未代用户勾选。
