const CATEGORY_NAMES = Object.freeze({
  competition: '学业竞赛',
  academic: '学业成绩',
  academic_innovation: '学术创新',
  research: '学术成果',
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
      includedScore: entry.included_score,
      included: entry.included,
      reason: entry.exclusion_reason,
      updatedAt: entry.updated_at,
      allowedActions: entry.allowed_actions || []
    }
  })
}
