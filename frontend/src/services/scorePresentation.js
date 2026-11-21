const CATEGORY_NAMES = Object.freeze({
  competition: '学业竞赛',
  academic: '学业成绩',
  academic_innovation: '学术创新',
  research: '学术成果',
  innovation_training: '创业创新',
  research_paper: '科研论文',
  invention_patent: '发明专利',
  certification: '能力认证',
  language: '外语能力',
  student_work: '学生工作',
  social_work: '社会工作',
  social_practice: '社会实践',
  honor: '荣誉称号',
  honor_title: '荣誉称号',
  competition_evidence: '其他竞赛',
  volunteer: '志愿服务',
  international_internship: '国际实习',
  military_service: '参军入伍',
  sports: '文体活动',
  comprehensive: '综合表现'
})
const STATUS_NAMES = Object.freeze({
  current: '当前有效',
  superseded: '历史版本',
  stale: '待更新',
  draft: '草稿',
  submitted: '待审核',
  under_review: '审核中',
  verified: '已核验',
  scored: '已计分',
  approved: '已通过',
  rejected: '已驳回',
  needs_correction: '待补正',
  unreviewed: '待审核',
  rule_unmatched: '未匹配计分规则',
  rule_available: '待确认规则',
  verified_not_eligible: '已核验，未满足计分条件',
  no_authoritative_snapshot: '暂无计分记录',
  invalidated: '已失效'
})
export const scoreStatusText = (value) => STATUS_NAMES[value] || '待处理'

// 竞赛材料的级别与奖项来自规则包枚举，展示层只做中文映射，不参与任何计分判断。
const COMPETITION_LEVEL_NAMES = Object.freeze({
  national: '国家级',
  provincial: '省级',
  municipal: '市级',
  school: '校级'
})
const COMPETITION_AWARD_NAMES = Object.freeze({
  first_or_above: '一等奖及以上',
  first: '一等奖',
  second: '二等奖',
  third: '三等奖',
  excellence: '优秀奖'
})
export const competitionLevelText = (value) =>
  COMPETITION_LEVEL_NAMES[value] || (value ? String(value) : '—')
export const competitionAwardText = (value) =>
  COMPETITION_AWARD_NAMES[value] || (value ? String(value) : '—')

// 材料事件的 action 是后端枚举；直接渲染会让教师看到 competition_approved 这种机器码。
const MATERIAL_EVENT_NAMES = Object.freeze({
  created: '创建草稿',
  attachments_added: '上传原件',
  submitted: '提交审核',
  withdrawn: '撤回',
  abandoned: '放弃',
  reviewed: '审核',
  checked: '核对',
  competition_approved: '审核通过',
  competition_returned: '审核退回',
  competition_ocr_started: '发起识别',
  competition_ocr_cancelled: '取消识别',
  competition_rule_invalidated: '规则失效',
  correction_version_created: '创建修正版本',
  confirmed_rule_and_submitted: '确认规则并提交',
  mark_rule_available: '标记规则可用',
  save_unmatched: '保存为未匹配'
})
export const materialEventText = (value) =>
  MATERIAL_EVENT_NAMES[value] || (value ? String(value) : '未知动作')
export const reviewDecisionText = (decision) =>
  decision === 'approve'
    ? '已通过'
    : decision === 'return' || decision === 'reject'
      ? '已退回'
      : '—'
export const scoreRuleVersions = (dto) =>
  (dto?.rule_versions || [])
    .map((v) => v.label)
    .filter(Boolean)
    .join('、') || (dto?.rule_version_ids?.length ? '历史计分规则（版本信息待补全）' : '无')
export function scoreFormulaText(formula) {
  if (!formula) return '暂无计算公式'
  const words = {
    academic_score: '学业基础分',
    academic_weight: '学业成绩权重',
    academic: '学术专长计入分',
    comprehensive: '综合表现计入分'
  }
  const translated = String(formula)
    .replace(/\b(?:academic_score|academic_weight|academic|comprehensive)\b/g, (key) => words[key])
    .replace(/\*/g, '×')
    .replace(/\//g, '÷')
  return /[A-Za-z_]/.test(translated) ? '计算公式说明待补全' : translated
}
const timeFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23'
})
export function formatScoreTime(value) {
  if (!value) return '—'
  let source = String(value).trim()
  if (!/^\d{4}-\d{2}-\d{2}T/.test(source)) return '—'
  if (!/(Z|[+-]\d{2}:\d{2})$/i.test(source)) source += 'Z'
  const time = new Date(source)
  if (!Number.isFinite(time.getTime())) return '—'
  const parts = Object.fromEntries(timeFormatter.formatToParts(time).map((p) => [p.type, p.value]))
  return `${parts.year}年${parts.month}月${parts.day}日 ${parts.hour}:${parts.minute}:${parts.second}`
}

const comprehensiveCategories = new Set([
  'comprehensive',
  'international_internship',
  'military_service',
  'volunteer',
  'social_work',
  'sports',
  'honor_title'
])

export function scoreRows(dto) {
  return (dto?.entries || []).map((entry) => {
    const source = entry.project_source || {}
    const category = source.category || 'unknown'
    return {
      id: entry.id ?? `${source.type}:${source.id}`,
      title:
        source.name ||
        `${CATEGORY_NAMES[category] || '证明'}材料${source.id ? '（编号' + source.id + '）' : ''}`,
      ruleLabel: entry.rule_label || '未匹配计分规则',
      group: comprehensiveCategories.has(category) ? 'comprehensive' : 'academic',
      verificationStatus: entry.verification_status,
      scoringStatus: entry.scoring_status,
      ruleVersionId: entry.rule_version_id,
      sourceVersion: entry.source_version,
      sourceType: source.type,
      sourceId: source.id,
      category,
      candidateScore: entry.candidate_score ?? entry.automatic_score,
      includedScore: entry.item_bonus ?? entry.included_score,
      included: entry.included,
      reason: entry.exclusion_reason,
      updatedAt: entry.updated_at,
      allowedActions: entry.allowed_actions || []
    }
  })
}
