# 平台截图三项一致验证（2026-11-20）

用户最新授权：匹配信用/荣誉时数页面即按普通志愿服务核对；信用使用有效签到签退并取签退日，荣誉使用录入日。覆盖上一轮缺类别/认定日期必须打回的约定。

使用独立新建SQLite、真实Flask HTTP、真实PP-OCRv5模型和带租约队列执行7张本地样本；填写值是预先确定的测试事实，不从OCR结果回填。

| 样本 | 页面 | 工时 | 服务记录日期 | 三项比较 |
|---|---|---:|---|---|
| example1.jpg | 荣誉 | 12 | 2026-09-14 | 三项一致，待提交 |
| example2.jpg | 信用 | 5.05 | 2025-12-21 | 三项一致，待提交 |
| example3.jpg | 荣誉 | 11.5 | 2026-09-18 | 三项一致，待提交 |
| example4.jpg | 信用 | 0.94 | 2026-04-06 | 三项一致，待提交 |
| example5.jpg | 信用 | 3.42 | 2026-11-06 | 三项一致，待提交 |
| example6.jpg | 信用 | 3.2 | 2026-11-06 | 三项一致，待提交 |
| example7.jpg | 荣誉 | 5.02 | 2025-12-09 | 三项一致，待提交 |

27次真实HTTP请求、9个真实模型队列任务（7个实际截图+2个既有一致/差异申诉回归），全部通过；教师审核和计分回归仍为一条有效计分0.0500。

完整后端711 passed/4 skipped；mounted72 passed/1 skipped；Node58 passed；构建通过。负例覆盖三项分别填错、缺关键时间、低质量时间、倒置时间及跨日。不会改写学生申报或自动跳过教师审核。

命令：`.venv/Scripts/python.exe -B openspec/changes/add-volunteer-ocr-appeals/evidence/check_live_flow.py --platform-all`。
证据：backend/outputs/volunteer-ocr/platform-all-live.log、platform-policy-live-results.json、policy-backend.log、policy-mounted.log、policy-node.log、policy-build.log。私有图片和输出未加入Git。

原API key仍为award_date，志愿服务页面显示为服务记录日期；OCR报告保存platform_policy及volunteer-material-3版本，原始提取与解释分别保留。Web/worker重启后沿用gradpush-dev.db，没有改写已有数据或历史OCR快照。旧记录需点击重新识别。

本轮未执行浏览器自动化；用户手动浏览器验收仍待完成，不以API或mounted测试冒充。未验证生产PostgreSQL或其他操作系统。
