# 证据（2026-11-23）

## 本地准备与归属

- 实际目标：backend/instance/gradpush-dev.db，原有1名学生、3个账号、7份材料、3个计分条目；以SQLite backup API在线备份到 backend/outputs/thousand-students/before-seed.db，并验证 integrity_check=ok。保留原有业务记录和账号密码。
- 政策PDF SHA-256与AGENTS.md一致；实际渲染阅读第4、5、6、7、9、10页。未修改计分公式、正式规则包及规则草稿。
- 独立命名空间 scale28_，四个主样本专业和一个空专业，另有边界流程专业；实际私有附件为有效PDF并标注合成测试。
- 生成工具：backend/tools/exercise_thousand_students.py；实际业务用例生成材料、附件、提交、审核和快照。志愿PDF使用真实OCR不支持格式退回后申诉路径，没有伪造识别成功。
- 补充工具：backend/tools/verify_scale_boundaries.py、backend/tools/exercise_scale_journeys.py；前端实测导出：frontend/tests/scale-report-export.mounted.test.js。

## 发现并修复

教师非竞赛汇总遗漏research_paper、invention_patent、innovation_training。新增test_scale_teacher_summary.py在修复前实际失败（pending_count=0，期望3），修复后通过；汇总现在使用后端材料能力集合，保持学院隔离。该修复归本次规模测试发现问题，不改变其他变更的验收状态。

教师竞赛工作台先截取最新50条再筛选待审，导致较旧待审不可见，历史也无继续加载入口。新增70条待审+60条新草稿+65条已处理的回归在修复前实际失败（items=0，期望50）；现改为按状态筛选后稳定游标分页，并为待审/历史分别提供加载更多。挂载交互验证分页、去重、失败保留列表与重试。

大批量材料暴露读取性能问题：`GET /api/materials/competition/records?reviewed=1&limit=100&year=2028`返回100条实测7.532秒。附件、事件、计分记录缺少按material_record_id/record_id的读取索引；新增三个索引后，同库同接口两次分别0.218秒、0.220秒（均200、100条）。这是单机观察值，不是并发吞吐或SLA保证。原始测量见list-before-index.json/list-after-index.json；局部SQLite索引迁移升级/回退/再升级及prepare_local重复准备测试6 passed，未执行生产迁移。

扩容至约690人时并行运行另一写入旅程，SQLite发生`database is locked`，该请求未通过，不宣称并发验收成功。已停止并行写入，将在填充完成后串行重跑并保留失败日志。并发锁问题本次未作为产品修复，不应隐藏为环境成功。

## 已执行回归

- `.venv/Scripts/python.exe -u backend/tools/exercise_thousand_students.py --database-file backend/instance/gradpush-dev.db --students 1000`：2026-11-23 21:37（北京时间）完成主样本生成，1000人、28000份，每人恰好28份、14类，生成阶段逐人差异0。实际SQL复核min/max材料数=28/28，类别数=14/14，foreign_key_check无违反。完整账号校验和后续报表步骤继续执行，不能由生成阶段代替。
- 主样本分布为规模测试专业1～4各250人，空专业0人。教师与管理员实际报表路由逐一返回200，人数250/250/250/250/0。

- `.venv/Scripts/python.exe -m pytest backend/tests/test_scale_teacher_summary.py backend/tests/test_arts_sports_material.py backend/tests/test_competition_base_scoring.py backend/tests/test_score_allocation.py backend/tests/test_student_score_snapshot.py backend/tests/test_score_explanation_api.py backend/tests/test_teacher_material_visibility.py backend/tests/test_research_scoring.py -q`：70 passed。既有SQLAlchemy事件警告4条；后续对全体Student兼容字段另行核对，不能仅凭警告认定数据正确。
- `cd frontend; npm.cmd run test:mounted -- tests/teacher-report-detail.mounted.test.js tests/teacher-home-count.mounted.test.js tests/teacher-statistics-mode.mounted.test.js tests/competition-workflow.mounted.test.js`：47 passed。

- 竞赛/计分领域与教师列表相关回归：236 passed、1 skipped（见regressions.log）；创新/干部审核与志愿政策/OCR路由补充：57 passed（见supplemental-regressions.log）。未将跳过项算作通过。
- 完整默认挂载套件：150 passed、3 skipped；启用真实规模报表fixture后，另有2项规模挂载导出测试通过。实际组件生成八个Excel，重新读取后逐单元格与DOM及1000名学生独立期望分核对一致。
- 主样本最终summary.json：3030/3030自动检查通过，score_mismatches=[]，包含全体账号密码验证、逐人成绩说明、教师/管理员逐专业报表、同分名次、权限、排名草稿与审计导出。
- 独立边界账号scale28_journey：106/106实际路由步骤/断言通过，27份材料覆盖全部14类；创新封顶2、干部封顶2、C类递补、专利补正失分、重复提交409、撤回与竞赛退回补正链全部验证。最终学术原始34、封顶15、综合表现3、总分82。

## 最终补充与交接

- `verify_scale_boundaries.py`全量检查完成，最终49/49通过：所有主样本候选分与Student兼容字段核对、真实验证码/密码登录代表账号、六类材料完整游标遍历、教师待审500条/10页与历史4007条/81页无漏项、无效请求原子拒绝、角色权限、导出审计、28000份附件存在且SHA-256完全一致。
- 首轮幂等重放测试误用了另一审核人，返回409符合跨审核人保护，不是产品缺陷。保留boundary-checks-initial.json，并以`verify_scale_boundaries.py --retry-review`只重跑纠正后的同审核人重放200、不同审核人409与不重复计分检查；其余已通过的全量读取/附件证据不重复执行。汇总链见boundary-summary.json与review-retry-checks.json。
- 索引补齐前后贯穿首轮分页检查，因此competition_1_all_pages的178秒总耗时不代表索引补齐后的耗时；单独前后对照接口测量已记录于上文。
- 后端额外跳过项为未提供私有证书样本；默认前端跳过项为API route audit缺manifest和两个需显式开启的规模fixture测试，后两个已独立开启执行通过。没有计为实际OCR成功或浏览器通过。
- 交接文件：backend/outputs/thousand-students/ACCEPTANCE.md（8项人工检查、账号、基线样本、限制和重启命令），accounts.csv，expected-scores.csv，八份实际组件导出的Excel，scale-test-review.zip。完整原始证据保留在同目录，未提交数据库/原件/会话到Git。
- 新增1000名主样本学生+1名边界学生，主样本28000份+边界27份材料；另保留原有1名学生与7份材料。原有业务核心表逐行比较结果见original-data-preservation.json。
- 用户真实浏览器教师/管理员验收仍未完成，任务5保持未勾选；并行SQLite写入锁冲突尚未作为产品修复。

## 环境限制

直接访问127.0.0.1:5001的网络套接字被执行环境拒绝（WinError 10013）。接口验证使用真实Flask路由测试客户端和目标SQLite，不冒称真实TCP HTTP或真实浏览器验收。禁止浏览器自动化，教师端与管理员端由用户人工验收。未执行生产数据库、并发负载、真实OCR识别成功、移动设备或视觉验收。现有backend/app.py关闭自动重载，计数修复需用户重启正在运行的后端才生效。
