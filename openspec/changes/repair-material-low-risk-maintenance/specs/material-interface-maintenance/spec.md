## ADDED Requirements

### Requirement: 互斥材料表单
志愿服务 SHALL 仅显示一份日期和工时字段；科研专用及其他材料表单保持可用。

#### Scenario: 志愿服务填写
- WHEN 学生打开志愿服务表单
- THEN 只有一个服务日期输入，保存沿用原字段并保留单次上传和预览。

### Requirement: 已迁移专利入口
旧申请入口 SHALL 拒绝创建invention_patent并返回409和新材料入口，历史记录不删除。

#### Scenario: 不带规则的专利请求
- WHEN 从旧接口使用applicationType、application_type或sub_type提交发明专利
- THEN 不产生Application，响应明确指向/api/materials/invention_patent/records。

### Requirement: 时间和能力语义
材料时间戳 SHALL 使用UTC ISO格式；类别计分能力 SHALL 与实际审核后规则能力一致，并独立于OCR标识。

#### Scenario: 工作台与详情相同时间
- WHEN 相同材料更新及审核时间出现在工作台、详情和事件中
- THEN 均带Z且代表同一时刻，纯日期保持不变。

#### Scenario: 科研、创新、干部材料
- WHEN 查询类别能力
- THEN 计分能力为true但不虚报新增OCR；人工核验类别不启用计分能力。
