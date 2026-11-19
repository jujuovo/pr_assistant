import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  createWorkflowAdapter, presentationState, requireAllowedAction, workflowErrorMessage
} from '../src/services/workflowPresentation.js'

test('presentation state mirrors backend status, version and allowed actions', () => {
  const dto = { id: 7, version: 3, status: 'frozen', reason_code: null,
    updated_at: '2029-01-01Z', allowed_actions: ['view', 'request_correction'] }
  assert.deepEqual(presentationState(dto), {
    status: 'frozen', label: '已冻结', reasonCode: null, version: 3,
    updatedAt: '2029-01-01Z', allowedActions: ['view', 'request_correction']
  })
  assert.deepEqual(requireAllowedAction(dto, 'request_correction'), { version: 3 })
  assert.throws(() => requireAllowedAction(dto, 'publish'), error =>
    error.code === 'action_not_allowed')
})

test('thin adapter sends one command and never derives a next status', async () => {
  const calls = []
  const adapter = createWorkflowAdapter({ command: async (...args) => {
    calls.push(args); return { status: 'correction_required', version: 4 }
  } })
  const dto = { id: 7, version: 3, status: 'frozen', allowed_actions: ['request_correction'] }
  const result = await adapter.command(dto, 'request_correction', { reason: '来源有误' })
  assert.deepEqual(calls, [[7, 'request_correction', { reason: '来源有误', version: 3 }]])
  assert.deepEqual(result, { status: 'correction_required', version: 4 })
  assert.equal(dto.status, 'frozen')
})

test('version conflict refreshes authority once and preserves the rejection', async () => {
  let refreshes = 0
  const conflict = Object.assign(new Error('conflict'), { status: 409, code: 'version_conflict' })
  const adapter = createWorkflowAdapter({ command: async () => { throw conflict } })
  const dto = { id: 1, version: 1, status: 'draft', allowed_actions: ['publish'] }
  await assert.rejects(adapter.command(dto, 'publish', {}, {
    refresh: async () => { refreshes++ }
  }), error => error === conflict)
  assert.equal(refreshes, 1)
  assert.equal(workflowErrorMessage(conflict), '数据已被更新，请刷新后重新确认影响')
})
