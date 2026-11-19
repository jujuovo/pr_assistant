# OCR字段关联（整合后）

最终入口、完整业务字段及人工通道见[主干整合说明](../../docs/ocr-main-integration.md)。

| 识别类别 | 保存方式 |
| --- | --- |
| 蓝桥杯、计算机设计、挑战杯 | 正式目录的competition字段，原证书信息在evidence；不符合正式目录级别时可主动选择competition_evidence仅核验 |
| 中国软件杯 | competition_evidence，保留作品、参赛人、等级、编号和日期；只人工核验 |
| CSP | 正式competition需补百分位；只保留成绩时为certification，五题成绩及总分独立保存 |
| 社会实践 | social_practice，区分证明、平台截图和名单 |
| 任职证明 | student_work，保留组织、职务、年月原文，具体日期及考核由学生补充 |
| 成果检索报告 | research，不推断论文归属或分区 |

GET /api/ocr/jobs/{id}返回原始report、mapping及受保护原图。POST /api/ocr/jobs/{id}/confirm-material经学生确认后保存材料；新建传year/data，已有传material_record_id/version/data。可选manual_only=true主动保存为人工材料，不生成分数。正式竞赛禁止关联旧Application，其他兼容材料可选择本人同院草稿申请。

前端使用ocrApi.js上传、轮询与确认，materialApi.js处理正式提交、补正和审核。CompetitionOcrJob与通用OCRJob共用版本绑定的实际队列；取消/迟到不会覆盖确认值。

原件确认前重查SHA-256，附件、关联及事件同事务保存；首次确认快照不被后续编辑覆盖。教师只能读取同院已提交材料，不能经OCR任务地址绕过草稿权限。
