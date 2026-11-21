# 设计

将手填表单改为volunteer / policy / generic互斥分支，保留原输入状态及上传预览。将invention_patent补入旧入口映射，支持原有驼峰、下划线与sub_type字段写法，不删除旧记录。

材料时间序列化统一使用utc_timestamp：既有naive DateTime解释为UTC，aware值转换为UTC，空值保持null；纯业务日期不改。覆盖材料详情、事件、最近审核和竞赛工作台。

RULE_SCORING_CATEGORIES明确六类已接计分类别。auto_bonus_enabled为类别能力，单条资格仍由固定规则和allowed_actions控制；不改变OCR状态。人工核验类别仍为false。

当前说明文档和历史交付记录分别标明现状、历史边界。CI双prepare用于幂等，不删除。Git已有cache/忽略规则，取消追踪单个会话文件即可，无需删除本地缓存。
