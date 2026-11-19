# 设计

- CompetitionOCR 继续复用 PP-OCRv5 mobile 与既有 ZigZag；图片最大10MB，通用识别不支持PDF，手工路径继续支持附件。
- /api/ocr 返回不可变 report、字段 mapping 和受保护原图；学生显式确认才创建或更新材料。
- 正式竞赛字段统一为 competition_id/project_name/award_date/level/award/event_year/participation_mode 及条件字段；补充证书事实放在 evidence。目录及候选分只由后端规则包提供，原始分数不推算CSP百分位。
- 页面绑定的 CompetitionOcrJob 与 OCRJob 使用同一任务ID。识别复用租约队列，发布时同时完成版本绑定检查；取消和迟到仅留诊断结果，不改学生确认值。
- 中国软件杯及显式不申请计分的获奖证明保存为 competition_evidence；CSP仅保存认证成绩时为certification。social_practice、research及OCR任职材料可仅核验；这些材料不调用正式计分。
- OCR任务只能确认一次；已有材料更新沿用edit_material和版本CAS；附件及确认关联同事务，失败删除本次新增私有文件。提交、补正、规则包绑定及审核保留远端用例。
- 教师不能通过OCR任务地址绕过草稿/组织权限。审核保留原始结果、首次确认及当前事实快照。
- 旧CertificateAssessment历史兼容保留；生产默认拒绝旧预览新建。仅历史回归夹具显式开启旧创建能力，不开放客户端配置。
- 不修改已发布规则/分数/排名历史；没有生产环境验证时不宣称生产迁移或完整 UI 验收通过。
