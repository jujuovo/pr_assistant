# 本地OCR与远端主干整合

## 最终业务入口

学生的“学业竞赛”使用MaterialRecord + CompetitionRulePackage + ScoreEntry。上传图像先识别，点击使用建议后核对表单，显式保存才写入材料，提交后由教师核对原件并审核，通过后使用固定规则计分。识别不会自动提交、批准或修改分数。

学生的“我的材料 → 其他证书识别与核验”支持社会实践、任职证明、成果检索及目录外竞赛。中国软件杯保持可识别，因不在正式目录只人工核验。已在目录中但级别不适用的证书，也可主动选择“不申请计分，仅保存人工核验材料”。CSP仅保存认证成绩时为人工核验；按正式项目计分时必须另填官方百分位，不从总成绩推算。

教师的待审核页同时提供竞赛审核及其他材料人工核验。管理员数据管理页可查看人工待核验及历史记录，竞赛规则与排名继续使用远端受控页面。

## 接口对应

| 前端 | 后端 |
| --- | --- |
| ocrApi.recognize/getJob/getMapping | POST /api/ocr/{key}/recognize；GET /api/ocr/jobs/{id}、/mapping |
| ocrApi.confirmMaterial | POST /api/ocr/jobs/{id}/confirm-material；新建year/data，已有material_record_id/version/data；可选manual_only=true |
| materialApi.start/get/cancelCompetitionOcr | /api/materials/competition/records/{id}/ocr、/{job_id}、/{job_id}/cancel；真实worker已接入 |
| materialApi.create/update/submit/reviewCompetition | 竞赛数据采用competition_id/project_name/award_date/level/award/event_year/participation_mode；证书补充字段在evidence |
| materialApi.listRecords/review | 人工类别使用同一records路径；reviewed=1读取同院历史，人工核验不会计分 |
| certificateApi.createPreview | 已弃用新建，生产默认409并返回新入口；历史预览读取与审核兼容保留 |

未实现OCR的academic/language/honor仍保留明确501与结构化输入。通用OCR只处理单张图片；PDF在本次新入口走人工原件核验，不伪装为已完成识别。

## 部署与验证

迁移顺序：20261110_workflow_indexes → 20261118_ocr_jobs → 20261118_ocr_links。新表保留OCR任务、材料关联及确认快照，不改正式规则包内容。已有生产库升级应先在隔离副本验证；本次没有修改业务库。

本地正式准备：`.venv/Scripts/python.exe -B backend/tools/prepare_local.py --database-file backend/instance/integration-fresh-20261119.db`。该路径是此次全新测试库，新的默认Windows库为backend/instance/gradpush-dev.db，Mac库为.local-mac/gradpush-dev.db；原certificate-local.db和app.db保留。当前联调的独立库仍保存作验收证据。

接口核对：先运行backend/tools/export_api_routes.py，再设置API_ROUTE_MANIFEST为生成的backend/outputs/integration-api-routes.json，运行npm run test:mounted --prefix frontend。清单核对方法/路径，不替代载荷校验、鉴权测试或浏览器验收。

具体命令、测试结果及未测范围记录在openspec/changes/integrate-local-ocr-main/evidence/validation.md。原align-three-role-core-workflows剩余页面问题仍由原变更跟进，不以本次整合冒充全部产品验收。


人工直接填写使用同一POST /api/materials/{category}/records的multipart请求，year与JSON编码data加files字段，后端同一事务创建材料和原件；不先创建空草稿再由前端串联上传。学生工作显式manual_only=true时只核验，未显式选择的既有规则流程保留。

最终结果：后端常规654通过、4个真实模型用例另行验证；前端Node57、mounted38及构建通过。接口路径/方法覆盖133个适配函数及21处页面请求；真实浏览器验收尚待用户反馈。详见上述验证记录对首次真实兼容测试失败与修复复测的说明。

校方来源导入保留历史竞赛字段兼容，OpenAPI以LegacyCompetitionData单独声明；正式竞赛创建采用CompetitionData，二者不混用。
