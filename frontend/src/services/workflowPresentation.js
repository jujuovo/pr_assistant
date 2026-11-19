const STATUS_LABELS = Object.freeze({
  draft: '草稿', submitted: '待审核', under_review: '审核中', needs_correction: '待修正',
  scored: '已计分', stale: '已失效', frozen: '已冻结', correction_required: '纠错中',
  published: '已发布', withdrawn: '已撤回', current: '当前', superseded: '历史版本'
})

const ERROR_MESSAGES = Object.freeze({
  version_conflict: '数据已被更新，请刷新后重新确认影响',
  source_version_conflict: '来源版本已变化，请刷新后重试',
  idempotency_conflict: '同一请求标识不能用于不同操作',
  derived_fields_read_only: '分数和排名由系统生成，不能直接编辑',
  forbidden: '没有执行此操作的权限'
})

export function presentationState(dto) {
  if (!dto || typeof dto !== 'object') throw new TypeError('展示对象不能为空')
  if (!Number.isSafeInteger(dto.version) || dto.version < 1) throw new TypeError('展示对象缺少有效版本')
  if (!Array.isArray(dto.allowed_actions)) throw new TypeError('展示对象缺少 allowed_actions')
  return Object.freeze({
    status: dto.status,
    label: STATUS_LABELS[dto.status] || dto.status || '未知状态',
    reasonCode: dto.reason_code || null,
    version: dto.version,
    updatedAt: dto.updated_at || dto.generated_at || null,
    allowedActions: Object.freeze([...dto.allowed_actions])
  })
}

export const workflowErrorMessage = error =>
  ERROR_MESSAGES[error?.code] || error?.message || '操作失败，请刷新后重试'

export function requireAllowedAction(dto, action) {
  const state = presentationState(dto)
  if (!state.allowedActions.includes(action)) {
    const error = new Error('后端未允许当前操作')
    error.code = 'action_not_allowed'
    throw error
  }
  return { version: state.version }
}

// 薄 adapter 只转发后端给出的版本和单一命令，不推导下一状态，也不串联写接口。
export function createWorkflowAdapter(api) {
  if (!api || typeof api.command !== 'function') throw new TypeError('adapter 需要 command API')
  return {
    async command(dto, action, input = {}, { refresh } = {}) {
      const { version } = requireAllowedAction(dto, action)
      try {
        return await api.command(dto.id, action, { ...input, version })
      } catch (error) {
        if ((error?.status === 409 || error?.code === 'version_conflict') && refresh) {
          await refresh()
        }
        throw error
      }
    }
  }
}
