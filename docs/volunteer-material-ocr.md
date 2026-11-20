# 志愿服务工时材料OCR

## 当前识别规则（用户2026-11-20确认）

学生手填本次工时、工时类别、服务记录日期，并一次上传证明。正确匹配“信用时数详情”或“荣誉时数详情”界面后，OCR规则将该截图的工时类别设置为普通志愿服务；不要求截图另外打印工时类别。

- 信用时数：从版面中心提取显示时数，用文字坐标分别提取签到、签退时间，校验时间顺序，服务记录日期取签退当天。跨日活动同样取签退日期。
- 荣誉时数：提取显示时数和平台录入时间，服务记录日期取录入当天，不使用录入原因中的活动日期。
- 三项均与学生申报相符：显示三项“一致”、状态“待提交”，学生正式提交后进入教师人工审核。
- 任一申报不符、界面不匹配、关键时间缺失或识别质量不足：打回并显示原因，可填写申诉理由转人工重点审核。

这是用户明确授权的项目内识别规则，不是OCR识别出了截图中不存在的类别文字。报告分别保留原始坐标提取与platform_policy解释，版本volunteer-screen-20261120-v1。自动一致不证明截图真实性，也不跳过教师审核。

原API沿用award_date字段名，志愿服务界面统一显示“服务记录日期”，其含义已改为上述截图日期，而不是教师审核通过日期。其他材料的获奖日期含义不变。推免周期由启用周期带入并只读，与截图记录日期分开。

## 队列与审核

保存后任务在后台持久队列执行，学生可以离开页面继续上传其他材料。“我的材料”展示进度、三项比较和逐份OCR报告。缺失值保留为未知，不补成0。申诉必须填写理由，进入待审核并标记“申诉材料 · 重点核验”，保留原申报、识别结果和原件。

教师通过后沿用既有累计工时计分。原始小时不提前减半；学生申报大型赛会或支教却上传上述普通截图时，会报告类别不一致，不静默改写学生申报。其他格式证明仍可人工核验。多张材料按明确类别累计原始小时；同一份申报只能有一个服务记录日期，不同日期请分次提交。相同图片不重复累计。

## 实现与部署

主项目复用services/recognition/volunteer.py的坐标提取逻辑，不依赖LAB目录。services/recognition/volunteer_material.py应用平台界面规则。保留低质量图标过滤前的platform_baseline；仅在多候选歧义时过滤极低质量字形重试，多个可读数字候选仍不直接通过。

Web与recognition_worker.py共用同一数据库。按README准备本地模型，运行start-local.ps1。prepare_local兼容已有开发库，正式Alembic部署需先备份并升级20261120_volunteer_ocr迁移。不修改旧数据库、已发布分值或历史识别快照。

## 接口

- POST /api/materials/volunteer/records（multipart）：手填字段和原件，自动入队，返回201。
- POST /api/materials/volunteer/records/{id}/ocr：{version}，重新识别当前原件，返回202。
- POST /api/materials/volunteer/records/{id}/submit：{version}，三项当前一致才允许普通提交。
- POST /api/materials/volunteer/records/{id}/appeal：{version,reason}，本人系统打回材料申诉，返回待审核材料。
- GET材料列表/详情：返回volunteer_ocr、appeal、priority_review及后端allowed_actions。

## 验证

backend/tests/test_volunteer_material_ocr.py包括信用、荣誉三项一致以及工时/类别/日期填错、跨日、时间倒置、缺失/低质量时间、队列、申诉和教师计分。
frontend/tests/volunteer-ocr.mounted.test.js包括两种页面三项一致、正式提交，以及预览、打回、申诉等交互。

本地私有样本位于被Git忽略的backend/samples/VolunteerHours。check_volunteer_samples.py用于真实模型批量识别，可选--reference-extractor比对实验程序的原始提取值。独立新库+真实HTTP+真实模型全链路验证：

```powershell
.venv/Scripts/python.exe -B openspec/changes/add-volunteer-ocr-appeals/evidence/check_live_flow.py --platform-all
```

输出位于backend/outputs/volunteer-ocr。历史记录请点击“重新识别”，无需重新上传；历史快照不会被静默替换。真实浏览器由用户手动验收，其他平台与生产数据库尚未验证。
