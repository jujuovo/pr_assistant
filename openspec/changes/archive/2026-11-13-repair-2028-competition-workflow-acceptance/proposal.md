# Proposal

## Why

已归档的 `implement-2028-competition-scoring-flow` 在契约、领域和后端测试层完成了大量工作，但真实本地启动暴露出归档验收与用户可用性不一致：竞赛页面仍是裸 HTML 契约壳，fresh database 未准备 2028 current 规则包，目录请求返回 404 且错误被泛化，学生无法完成草稿申报。必须以独立纠正 change 补齐原 change 已承诺但未被真实证据证明的运行时与前端闭环，同时保持归档历史不可改写。

## What Changes

- 建立竞赛工作流界面与运行时就绪契约：页面必须具备与现有设计系统一致的布局、响应式表单、加载/空/阻塞/错误/成功状态和可访问交互，而非只提供可编译的裸控件。
- 让竞赛申报从后端权威周期与 current `CompetitionRulePackage` 获取上下文，消除页面和目录读取路径中散落的 `2028` 假设；正式规则数据仍保持 2028 政策内容不变。
- 修复 fresh local database 的初始化/阻塞语义：启用竞赛入口时必须装载唯一正式包，无法装载时页面明确说明配置阻塞并禁止产生无依据材料，不以空目录冒充可申报状态。
- 重构学生竞赛申报请求编排，避免父子组件重复加载；目录、详情、材料、OCR/手填、附件、提交、补正、重新确认和反馈均呈现可恢复状态。
- 修复错误映射，保留后端稳定 code 与可操作说明；缺少 current 包、权限、版本冲突、重复材料、附件缺失及服务失败不得统一显示为“核对材料”。
- 补齐真实 Vue 组件挂载测试、fresh database 启动集成测试和浏览器端学生→教师→学生闭环，记录网络状态、页面状态和视觉证据。
- 明确 prior build、纯函数测试和源码字符串断言只作为辅助证据，不再作为组件/E2E 或产品可用性通过依据。
- 范围外：修改 2028 正式计分矩阵、2029 规则包复制编辑、正式排名发布、迁移非竞赛 `Application` 类别，以及重写已归档 change1 的历史工件。

## Capabilities

### New Capabilities

- `competition-workflow-interface`: 定义竞赛新链路在权威周期/规则包依赖、学生与教师页面状态、产品级交互、可操作错误和真实运行验收方面的行为。

### Modified Capabilities

- `academic-competition-scoring`: 明确正式目录必须通过可用的 current 规则包暴露，客户端不得以硬编码周期或空目录代替后端权威上下文。
- `material-evidence-review`: 明确竞赛 OCR/手填、附件、提交、补正和审核旅程必须在依赖缺失与失败状态下保持可解释、可恢复，且不得发出重复或越权请求。

## Impact

- 前端：`CompetitionWorkflow.vue`、`MaterialWorkflow.vue`、学生材料入口、教师竞赛审核页面、API adapter、共享状态/错误组件及相应样式。
- 后端与本地环境：current 竞赛上下文读取契约、`prepare_local.py`/demo seed 的正式包就绪或显式阻塞、稳定错误响应；不改变正式政策算法。
- 测试与证据：Vue 挂载/交互测试、fresh SQLite 集成测试、真实浏览器三角色关键旅程、网络与截图记录，以及现有后端/构建回归。
- 兼容：竞赛继续唯一使用 `MaterialRecord + CompetitionRulePackage + ScoreEntry`；非竞赛 `Application` 兼容入口保持原范围且不得被本 change 扩展。
- 历史与审计：归档 change1 保持不可变；本 change 仅记录并纠正其后发现的验收缺口。
