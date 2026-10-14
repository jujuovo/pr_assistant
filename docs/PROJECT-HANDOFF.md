# 项目交接入口

当前运行/安装命令以根目录README为准；发布整理与测试状态见RELEASE-CHECKLIST.md。完成新模块后同步此文件和相关接口文档。

- frontend/src：Vue页面。学生申请入口pages/student/applications/ApplicationForm.vue。
- backend/blueprints/certificate_bp.py：蓝桥杯接口；services/certificates/preview.py：先识别后申报。
- POST /api/certificates/previews：私有上传并创建识别草稿。
- GET /api/certificates/applications/{id}：查询状态/报告/申报值。
- POST /api/certificates/applications/{id}/confirm-preview：保存或提交同一申请。
- CertificatePreview.vue展示可改申报表，CertificateReport.vue供教师同时查看OCR、申报值及原图。
- 学生修改直接作为申报值；原report/sources不覆盖，不设独立修改审批；教师审核整份申请。
- backend/seed/demo.json为Windows/Mac共享开发数据；tools/seed_demo.py为幂等加载器；tools/prepare_local.py负责开发库表结构准备。
- Windows库backend/instance/certificate-local.db；Mac库.local-mac/app.db；两端数据独立、均不提交Git。
- 后端5001、前端5173；Web与recognition_worker必须使用同一数据库、模型与材料目录。
- 旧申请只保留原流程结果；新预览需新建申请。替换文件会保留之前草稿。
- 待办：Windows实机与Actions验收；志愿OCR页面闭环；五类材料业务页面与未实现的通用识别。不要将蓝桥杯成功等同全部模块完成。
