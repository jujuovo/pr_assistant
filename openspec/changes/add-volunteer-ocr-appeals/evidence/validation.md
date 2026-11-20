# 验证记录（2026-11-20，Windows）

## 结果

- 后端完整回归：700 passed，4 skipped。命令：`.venv/Scripts/python.exe -B -m pytest backend/tests -q -p no:cacheprovider --tb=short`。日志：backend/outputs/volunteer-ocr-backend-tests.log。
- 最终相关回归：55 passed，1 skipped（新增志愿服务测试、迁移、接口契约、旧OCR回归）。日志：backend/outputs/volunteer-ocr-final-targeted.log。
- mounted：62 passed，1 skipped；包含新增6项志愿服务交互。命令：`npm --prefix frontend run test:mounted`。
- Node：58 passed，0 failed。对 frontend/tests/*.test.mjs 执行 node --test。
- 前端生产构建通过；保留既有chunk大小提示。命令：`npm --prefix frontend run build`。
- SQLite迁移新增绑定字段与索引，升级和降级保留原OCR任务。
- 旧开发库 prepare_local 升级前已用SQLite backup备份，前后 user=3、application=0、material_record=2，数量不变；certificate-local.db没有被修改。
- 真实本地HTTP + 新建SQLite + PP-OCRv5_mobile：13次请求、2个真实模型任务，第一份202小时一致→提交→教师无意见通过→0.0500分；第二份203小时申报与原件202小时不同→打回→申诉标记→教师驳回，仍仅一条有效计分0.0500。

## 重现真实HTTP检查

在仓库根目录运行：

```powershell
.venv/Scripts/python.exe -B openspec/changes/add-volunteer-ocr-appeals/evidence/check_live_flow.py
```

脚本生成新UUID命名的测试数据库及合成工时证明，使用官方prepare_local准备2028周期和28项正式规则包，临时启动5002端口的真实Flask后端，通过真实登录接口创建独立测试会话并运行真实模型，最后停止该临时服务。不操作浏览器，不删除或覆盖已有数据库。Windows默认字体为微软雅黑；其他环境需用--font提供中文字体，尚未验证。

输出：backend/outputs/volunteer-ocr/live-http-evidence.json、live-flow.log和synthetic-volunteer-proof.png。仅包含合成证据与开发测试数据；不代表实际学校平台截图准确率。实际模型输出正确提取202小时、regular、2026-05-08。

## 本地人工复验环境

http://127.0.0.1:5173/ 与 http://127.0.0.1:5001/api/public/system-info 均200；Web、worker共用backend/instance/gradpush-dev.db。进程记录在backend/outputs/integration-runtime.json。通过官方prepare_local完成可保留数据的准备，独立真实HTTP检查另用新测试库。

1. 学生：提交材料→志愿服务→手填三项→一次上传→保存并后台识别，立即离开，再到我的材料查看队列。
2. 一致材料：出现字段一致和正式提交入口，提交后教师人工审核，无意见可以通过。
3. 差异或不支持格式：自动打回，普通提交入口不可用，能查看具体原因及逐份提取结果。
4. 申诉：理由为空不可提交；填理由后进入待审核，教师端选择志愿服务，看到“申诉材料 · 重点核验”、申诉理由、原差异和原件。
5. 教师通过或驳回后，学生查看结果及加分统计；页面刷新、离开均不取消后台任务。

## 明确未验证

浏览器由用户手动操作，此次没有执行真实浏览器旅程或截图验收，该任务保持未勾选。未验证生产PostgreSQL迁移和锁、macOS、移动浏览器、实际平台截图准确率。OpenSpec CLI未安装，list/status/apply/validate命令不可用，不以文件存在代替验证。

既有SQLAlchemy SAWarning及弃用提示仍存在；回归未失败。保留后台模型初始化的可选ccache提示。接口文档同步新增志愿OCR/申诉路由、数据类型和字段；旧契约测试补入主干已有的志愿服务类别。旧迁移测试按新增后续迁移链比对当前模型；旧写入清单扫描排除outputs里的临时导出代码；导航测试改为验证主干已经采用的submissionQuery行为。
