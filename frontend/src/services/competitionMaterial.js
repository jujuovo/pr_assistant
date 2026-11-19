const FORBIDDEN = new Set(['rule_id', 'self_score', 'final_score', 'dynamic_coefficients', 'override_score', 'override_reason'])

export function legalCompetitionOptions(schema, level) {
  const awards = schema?.awards_by_level?.[level] || []
  return {
    levels: [...(schema?.levels || [])],
    awards: awards.filter(value => !(level === 'provincial' && value === 'third')),
    formats: (schema?.formats || []).filter(value => value !== 'invitation'),
    participationModes: [...(schema?.participation_modes || [])]
  }
}

export function buildCompetitionFacts(form, schema) {
  for (const key of Object.keys(form || {})) {
    if (FORBIDDEN.has(key)) throw new TypeError(`竞赛请求禁止字段 ${key}`)
  }
  if (!form.competition_id) throw new TypeError('必须从正式目录选择竞赛')
  const options = legalCompetitionOptions(schema, form.level)
  if (!options.levels.includes(form.level)) throw new TypeError('竞赛级别不在正式选项中')
  if (!options.awards.includes(form.award)) throw new TypeError('奖项不在正式选项中')
  if (form.event_format && !options.formats.includes(form.event_format)) throw new TypeError('赛制不在正式选项中')
  if (form.participation_mode === 'team') {
    const size = Number(form.team_size), rank = Number(form.personal_rank)
    if (!Number.isInteger(size) || size < 1 || !Number.isInteger(rank) || rank < 1 || rank > size) {
      throw new TypeError('团队总人数和本人排序必须有效')
    }
  }
  const keys = ['competition_id', 'project_name', 'award_date', 'level', 'award', 'event_year',
    'participation_mode', 'team_size', 'personal_rank', 'event_format', 'csp_percentile', 'group', 'track']
  return Object.fromEntries(keys.filter(key => form[key] !== '' && form[key] != null).map(key => [key,
    ['event_year', 'team_size', 'personal_rank'].includes(key) ? Number(form[key]) : form[key]]))
}

export function validateCompetitionForm(form, schema, evidencePeriod = {}) {
  const errors = {}
  const required = new Set(schema?.required || [])
  const labels = {
    competition_id: '正式目录条目', project_name: '项目名称', award_date: '获奖日期',
    event_year: '赛事年份', level: '级别', award: '奖项',
    participation_mode: '参赛方式', team_size: '团队总人数', personal_rank: '本人排序',
  }
  for (const key of required) {
    if (form?.[key] === '' || form?.[key] == null) errors[key] = `${labels[key] || key}为必填项`
  }
  const options = legalCompetitionOptions(schema, form?.level)
  if (form?.level && !options.levels.includes(form.level)) errors.level = '请选择正式规则允许的级别'
  if (form?.award && !options.awards.includes(form.award)) errors.award = '该奖项与所选级别不匹配'
  if (form?.award_date) {
    const value = String(form.award_date)
    if (evidencePeriod.start && value < evidencePeriod.start) errors.award_date = `获奖日期不得早于 ${evidencePeriod.start}`
    if (evidencePeriod.end && value > evidencePeriod.end) errors.award_date = `获奖日期不得晚于 ${evidencePeriod.end}`
  }
  const year = Number(form?.event_year)
  if (form?.event_year !== '' && (!Number.isInteger(year) || year < 2000 || year > 2100)) {
    errors.event_year = '赛事年份必须是 2000 至 2100 的整数'
  }
  if (form?.participation_mode === 'team') {
    const size = Number(form.team_size), rank = Number(form.personal_rank)
    if (!Number.isInteger(size) || size < 1) errors.team_size = '团队总人数必须是正整数'
    if (!Number.isInteger(rank) || rank < 1 || (Number.isInteger(size) && rank > size)) {
      errors.personal_rank = '本人排序必须是团队人数范围内的正整数'
    }
  }
  return errors
}

const ERROR_STATES = {
  competition_cycle_missing: ['configuration', '当前申报周期尚未启用，请联系管理员完成周期配置。'],
  competition_package_missing: ['configuration', '当前周期缺少正式竞赛规则包，请联系管理员完成发布后再申报。'],
  competition_package_invalid: ['configuration', '正式竞赛规则包未通过校验，请联系管理员重新发布。'],
  competition_context_cycle_mismatch: ['configuration', '申报周期与正式竞赛规则包不一致，请联系管理员修复配置。'],
  duplicate_submission: ['validation', '该竞赛材料已提交，请打开已有记录继续处理。'],
  invalid_competition_facts: ['validation', '材料事实未通过校验，请检查标记字段。'],
  competition_attachment_required: ['validation', '请先上传证明原件，再提交审核。'],
  forbidden: ['permission', '当前账号没有执行此操作的权限，请重新登录或联系管理员。'],
  version_conflict: ['conflict', '材料已被其他操作更新，请刷新权威状态后重新确认。'],
  competition_context_version_conflict: ['conflict', '竞赛规则上下文已更新，请刷新后重新确认。'],
  rule_package_changed: ['conflict', '竞赛规则已更新，请刷新并重新确认材料。'],
  REQUEST_TIMEOUT: ['backend-unavailable', '服务响应超时，输入仍保留；请稍后重试或先刷新权威状态。'],
}

export function competitionErrorState(error = {}) {
  const configured = ERROR_STATES[error.code]
  if (configured) return { kind: configured[0], message: configured[1], code: error.code }
  if (error instanceof TypeError || error.status === 400 || error.status === 422) {
    return { kind: 'validation', message: error.message || '请检查材料字段后重试。', code: error.code }
  }
  if (error.status === 401 || error.status === 403) {
    return { kind: 'permission', message: '当前会话或组织权限不足，请重新登录或联系管理员。', code: error.code }
  }
  if (error.status === 409) {
    return { kind: 'conflict', message: error.message || '权威状态已变化，请刷新后重试。', code: error.code }
  }
  return {
    kind: 'backend-unavailable',
    message: '服务暂不可用，问题不一定来自材料内容；输入已保留，请稍后重试。',
    code: error.code,
  }
}

export const competitionErrorMessage = code => competitionErrorState({ code }).message

export function ocrView(job, confirmedTerms) {
  return { status: job?.status || 'idle', raw: job?.raw_result || null,
    confirmed: { ...(confirmedTerms || {}) }, lateResultIgnored: Boolean(job?.late_result_ignored) }
}
