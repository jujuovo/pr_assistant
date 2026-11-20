# 证明图片预览与真实平台提取纠正

用户已手动发现旧界面缺缩略图、模块页混入跨类别选项、example2被误显示为0。此前合成证明测试不能证明实验截图兼容。修复不修改LAB目录、不修改用户申报和历史OCR快照。

2026-11-20 Windows结果：后端704 passed/4 skipped；mounted70 passed/1 skipped；Node58 passed；构建通过。日志位于backend/outputs/volunteer-ocr/preview-*.log。新增测试覆盖六个人工材料类别的选图→缩略图→点击放大→关闭，以及已选志愿模块不出现跨类别选择栏、缺字段时仍展示5.05和签到签退。

对backend/samples/VolunteerHours中7张本地图片运行真实PP-OCRv5并保存原始输出，随后以这些原始OCR数据复核修复后的提取器及实验extractor.py。原始提取字段全部等于实验基线；example4因图标被识别为低分“2”引入歧义，过滤极低质量字形后恢复0.94。过滤后的提取与对同样过滤输入运行的实验提取器一致。原始结果保留在platform_baseline，过滤标志为noise_filtered；不会过滤多个高质量数字候选。其余6张不触发过滤。

7个时数：12、5.05、11.5、0.94、3.42、3.2、5.02。example2签到2025-12-21 12:33:03，签退17:36:34；类别与认定日期没有从截图推断。

另运行真实后端独立端口5002、新建SQLite、真实模型3个队列任务和15次HTTP请求，包含example2原图，确认识别工时5.05匹配申报、缺类别及认定日期为null、仍打回且允许申诉；既有一致/差异/申诉/教师评分流程通过。命令：

```powershell
.venv/Scripts/python.exe -B openspec/changes/add-volunteer-ocr-appeals/evidence/check_live_flow.py --platform-sample backend/samples/VolunteerHours/example2.jpg
```

证据：backend/outputs/volunteer-ocr/repair-live-flow.log、live-http-evidence.json、platform-samples/summary.json。私有样本与输出未加入Git。部署只使用主项目代码和模型，不依赖实验目录。

本地Web和worker重启到修复代码，继续使用gradpush-dev.db，前端HMR更新。真实浏览器操作按仓库规则由用户手动完成，本轮仍待复验；未声称浏览器或生产平台验收通过。
