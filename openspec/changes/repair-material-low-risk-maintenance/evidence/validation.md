# 低风险维护验证（2026-11-21，Windows）

基线414dda8，分支fix/material-low-risk-maintenance-20261121。没有修改计分公式、OCR算法、数据库结构或历史业务数据。

## 逐项结果

1. 志愿表单改为volunteer / policy / generic互斥分支；mounted确认一个日期输入且没有额外generic字段，原上传和保存请求保持。相关三套表单测试24通过。
2. 发明专利补入MIGRATED_MATERIAL_ROUTES；不传rule_id、分别用applicationType/application_type/sub_type写入旧接口均409，返回新入口，不生成旧申请。专利与科研相关回归18通过。
3. cache/2029240f6d1128be89ddc32729463129取消Git跟踪；操作前后确认本地文件仍存在。cache/已有忽略规则，不重复添加，不删除本地会话。
4. 材料工作台、详情、事件及最近审核统一utc_timestamp，支持naive UTC、aware转UTC和null；接口集成用固定时刻确认四处表示同一瞬间。纯业务日期未改变。
5. auto_bonus_enabled补齐科研论文、发明专利、创新训练和学生工作，含原有竞赛与志愿共六类；OCR标识保持独立，人工核验类别仍false。元数据相关回归45通过。
6. 当前能力矩阵、初版接口文档、旧链路边界、交付说明和历史问题备忘同步；旧验证记录标明历史，不替代本轮验收。CI双prepare保留用于幂等验证。

## 全量检查

- 后端：818 passed，4 skipped；命令 .venv/Scripts/python.exe -B -m pytest backend/tests -q -p no:cacheprovider --tb=short，日志backend/outputs/maintenance-backend-full.log。
- 前端mounted：105 passed，1 skipped；日志maintenance-mounted-full.log。
- Node：62 passed；日志maintenance-node.log。
- npm --prefix frontend run build通过，保留既有chunk大小提示；日志maintenance-build.log。
- 在backend/outputs/maintenance-fresh-20261121.db独立新建库运行prepare_local成功，包含启用2028周期、28项正式竞赛目录和其他材料规则。未重置或迁移业务库。
- Git空白检查使用cr-at-eol允许既有Windows CRLF，未发现实际行尾空格。
- 本地Web、worker、前端使用原gradpush-dev.db启动，后端公开健康接口及前端首页均200。

## 用户手动验收（未代为执行）

1. http://127.0.0.1:5173/ 提交材料→志愿服务→打开表单，确认只有一份工时和服务记录日期；选择图片后仍可缩略图放大，保存原字段正常。
2. 打开科研论文/发明专利/创新训练表单，确认仍显示各自专用字段；文体及其他材料保留各自通道。
3. 我的材料和教师工作台的更新时间显示为正确北京时间，事件与更新时间不出现8小时偏差。

真实浏览器由用户操作，本轮未执行浏览器自动化、实际图片模型推理、生产PostgreSQL或其他操作系统验证。OpenSpec CLI不可用，未伪称list/status/apply/validate通过。

旧Application鉴权缺口与旧SQLite迁移缺陷不在本轮选定低难度项范围，仍未修复；计分业务上限、旧表退出及新增OCR未改动。
