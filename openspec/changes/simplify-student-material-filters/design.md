# 分组设计

仅将后端返回状态映射为前端筛选分组，不修改后端状态、计分或allowed_actions。保留workflow_state优先、status兜底的原有顺序。

待提交包含draft/ready_to_submit；识别中包含OCR排队/运行；待审核包含submitted/under_review/pending_review；已通过包含scored/verified/approved及已核验不计分，卡片仍明确显示不计分；需处理包含识别失败、退回补正和规则未匹配/待确认；驳回及放弃各自保留。全部继续包含未知未来状态。

筛选在已加载记录中进行，保留排序、加载更多、刷新、后台轮询、异常提示和历史兼容页。OCR完成移出识别中分组，用户可切换待提交查看。未新增页面或接口。
