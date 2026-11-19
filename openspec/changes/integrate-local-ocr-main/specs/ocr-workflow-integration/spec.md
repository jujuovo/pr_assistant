## ADDED Requirements

### Requirement: 识别结果必须经学生显式确认
系统 MUST 分别保存原图、OCR原始字段、映射建议与学生确认快照；OCR不批准材料或加分。

#### Scenario: 学生修改识别姓名
- **WHEN** 学生在预览中修改姓名并确认
- **THEN** 正式字段保存修改值，OCR原始姓名和原图不被覆盖

### Requirement: 正式竞赛复用唯一计分来源
系统 SHALL 将正式竞赛写入MaterialRecord并绑定正式规则包，不新建旧Application；教师通过后由既有计分用例处理。

#### Scenario: 审核请求重放
- **WHEN** 教师重放同一审核幂等请求
- **THEN** 返回既有结果且不增加第二条ScoreEntry

### Requirement: 非正式材料保留人工通道
系统 SHALL 为目录外或学生明确不申请计分的材料保存仅核验记录，不改变正式目录，不生成计分明细。

#### Scenario: 中国软件杯或省级蓝桥杯仅核验
- **WHEN** 学生将其保存至人工核验通道并由教师通过
- **THEN** 核验事件、原件和确认字段保留，但没有ScoreEntry或旧Application

### Requirement: CSP成绩不能推算排名
系统 MUST 保留CSP各题成绩与总成绩，正式计分需要学生另行提供百分位。

#### Scenario: 仅有260分成绩
- **WHEN** 学生尝试按正式CSP项目计分且未提供百分位
- **THEN** 系统提示缺少百分位，不从总成绩推算

### Requirement: 迟到识别不得覆盖确认事实
系统 MUST 将OCR任务绑定到材料版本，并隔离取消及版本过期后的结果。

#### Scenario: 停止识别后人工修改
- **WHEN** 被取消任务后来完成
- **THEN** 原始结果仅供诊断，不改学生申报值且不可用该任务确认覆盖

### Requirement: 前后端接口契约可重复核对
系统 SHALL 用实际Flask路由核对前端请求路径与HTTP方法，并以挂载交互验证学生确认及教师核验。

#### Scenario: 未适配考试材料
- **WHEN** 请求尚无OCR实现的类别
- **THEN** 不显示已识别，保留人工/结构化路径及明确错误
