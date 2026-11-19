# 本地 OCR 与远端主干整合

## Why
本地七类识别、ZigZag、原件校验及字段确认尚未提交；远端主干已转为 MaterialRecord + CompetitionRulePackage + ScoreEntry，并有学生、教师、管理员页面。直接合并会出现两套材料字段、未接入引擎的竞赛 OCR 队列、无规则的人工材料不能提交，以及旧预览继续新建 Application 的问题。

## What Changes
- 保留本地七类识别和远端正式竞赛审核计分，明确学生确认与原件的独立快照。
- 正式目录中的竞赛统一使用远端材料模型；旧蓝桥杯预览不再新建旧申请，历史读取和兼容审核保留。
- 用户明确选择：保留教师通过后的规则计分；中国软件杯不扩入正式目录；CSP成绩不推算百分位。
- 新增明确的仅人工核验通道，以及学生可选择的不计分保存方式，不产生 ScoreEntry。
- 对齐前端全部请求适配层及页面直接 fetch 的路径与方法，并保留原角色权限。
- 连接真实识别 worker、处理取消/迟到、并发与原件完整性；补充 mounted 交互与 API 回归。

## Ownership
本 change 负责合并与 OCR 接入，不勾选 align-three-role-core-workflows 的任务。其 9.4 已记录的 result=null 导致 /score/current 500 属于本次接口联调阻塞点，在原 use_cases/scoring.py 作小范围修复并补回归，仍由原 change 完成其产品级验收。归档目录保持不变。本 change 不承担原 9.2–9.8 的全部页面改版。

## Impact
增加 OCRJob/OCRMaterialLink 表的迁移接在远端唯一迁移头后；补充证书字段位于 JSON evidence，不更改正式规则包或既有分值。不覆盖业务数据库，使用新建测试库验收；生产 PostgreSQL 的升级、锁和回滚另行验证。
