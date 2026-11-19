# OCR字段关联

## 对应关系

| OCR项目 | 材料类别 | 主要业务字段 |
| --- | --- | --- |
| lanqiao | competition | competition_name、participants、advisers、school、edition、track、group、region、award_level、certificate_no、award_date |
| computer-design / software-design / challenge-cup | competition | competition_name、edition、participants、project_name、school、award_level、group、stage_as_printed、certificate_no、advisers、award_date |
| csp | certification | document_type、certification_name、subject_name、certificate_no、test_date、batch、language、test_site、task_scores、score、full_score |
| social-practice | social_practice | document_type及实践队名、成员、实践时间原文、开具单位、日期；平台截图的提交人、表彰信息、时间及显示状态；名单的可见队名 |
| other / appointment_proof | student_work | subject_name、start_month_as_printed、end_month_as_printed、appointments[].organization / position；具体日期、职务级别、考核结果及as_of需确认补充 |
| other / research_report | research | document_type、report_no、requester_school、database、publication_year |

原有academic、language、honor仍支持结构化填报、附件和人工核验；尚无对应的可运行OCR适配器，不标记为识别成功。原蓝桥杯/api/certificates的学生预览、声明和申请关联，以及志愿工时的claimed_hours与申请关联保持原流程。

## 识别到确认

1. GET /api/ocr/categories 查询项目；material_categories声明该项目支持写入的材料类别。材料字段目录使用GET /api/materials/types。
2. POST /api/ocr/{key}/recognize 上传单张图片，返回202和任务id。worker异步识别。此步不创建材料或申请。
3. GET /api/ocr/jobs/{id} 轮询，或GET /api/ocr/jobs/{id}/mapping仅读取字段映射。mapping包含material_category、data、missing_fields、warnings、provenance、unmapped_fields；任职证明另有source_hints。原始识别仍保存在report.fields。
4. 页面将mapping.data填入可编辑预览；学生核对、补齐missing_fields后，POST /api/ocr/jobs/{id}/confirm-material保存。不要在收到识别结果后自动确认。
5. 返回material，含正式data、ocr_links、原件attachments以及可选application_id。材料保持draft，再沿用材料的submit、check、review流程。

新建材料的确认请求示例：

```json
{
  "year": 2026,
  "application_id": 123,
  "data": {
    "certification_name": "CCF CSP",
    "subject_name": "学生确认的姓名",
    "certificate_no": "CCF-IDEN-CSP-2025-12345",
    "test_date": "2025-09-21",
    "score": 260,
    "full_score": 500,
    "task_scores": [100, 100, 40, 0, 20]
  }
}
```

application_id可省略；如提供，只允许本人同学院的草稿申请，系统不会创建申请或同步成绩。示例满分为学生确认值，OCR不会自动猜测。

关联或更新已有材料时，请求改为material_record_id、version、完整data及可选application_id，不传year。类别须与识别映射一致；仅允许本人draft或needs_correction材料。返回200；新建返回201。一个OCR任务只能确认一次，重复请求409；网络超时后先查询任务的material_record_id和material_url，避免重复上传。

已有材料也可先上传附件，再调用POST /api/materials/{category}/records/{record_id}/recognize，请求为：

```json
{"version": 2, "attachment_id": 45, "project_key": "csp"}
```

该入口校验材料版本、附件归属及摘要后创建识别任务；仍须显式调用confirm-material并携带material_record_id及当前version，才能写回该材料。无参数或尚未适配的类别保留501返回。

## 校验与来源

- 完整日期转换为YYYY-MM-DD；只有年月时保留原文，提示补充，不虚构某月1日。任职end_date=null表示仍在任，学生须明确确认。
- 赛段原文保存在stage_as_printed，不自动推断competition_level。主办单位与比赛级别须补充。
- CSP总分、满分需有效且总分不超过满分；提供五道题分时校验各题范围及合计。0分是有效成绩。认证不转换为获奖等级。
- 社会实践区分practice_proof、platform_screenshot、team_list，分别要求队名及实践时间、提交人及表彰名称日期、队名列表。截图显示的审核状态不等于学校已核验，队名也不证明个人参加。
- 成果报告不推断论文归属、期刊分区；未匹配other子类型的任务不能通过确认接口写入材料，应人工填报。
- 建议字段来自OCR；project_key、蓝桥杯名称、CCF CSP名称来自已选择的适配器目录。provenance记录字段取自哪个原始字段，不表示真实性置信度。

## 保存与审核

数据库关系为OCRJob → OCRMaterialLink → MaterialRecord → 可选Application。OCRMaterialLink以job_id为主键，保存suggestions、confirmed_snapshot、确认人及时间；材料后续修改不会覆盖最初确认快照或原始report。

确认前重新校验OCR输入原件SHA-256；原件复制到材料私有附件目录，已有相同摘要附件也须通过实际文件校验。创建、附件、关联及事件同事务保存，失败回滚并清除本次新文件。已有材料使用version进行并发保护。

材料详情返回ocr_links，教师可据result_url查看原始识别，artifact_urls查看原图及定位图，并对照当前data和confirmed_snapshot。所有读取沿用本人/同院教师管理员权限，只有原上传学生能确认。审核事件同时保存材料字段、附件摘要、OCR关联快照。

前端封装：frontend/src/services/ocrApi.js提供上传、轮询、映射、确认；materialApi.js支持新增材料类别及附件识别参数。当前完成接口和字段关联，尚未为所有类别增加完整的学生填写页面或教师审核页面。

## 部署与验证

既有数据库执行迁移至20261118_ocr_links。本地start-local.ps1使用prepare_local创建缺失表；本次未修改业务数据库。Web和worker须使用同一数据库和私有目录。

专项测试：

```powershell
.venv/Scripts/python.exe -B -m pytest backend/tests/test_ocr_material_fields.py -q -p no:cacheprovider
node --test frontend/tests/material-api.test.mjs frontend/tests/ocr-api.test.mjs
```

真实OCR测试设置RUN_REAL_OCR=1及本地OCR_MODEL_ROOT；覆盖蓝桥杯、CSP从识别到材料确认的链路。
