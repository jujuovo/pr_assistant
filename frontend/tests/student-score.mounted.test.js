// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { expect, test, vi, beforeEach } from 'vitest'
const state = vi.hoisted(() => ({ load: vi.fn(), score: null, detail: vi.fn() }))
vi.mock('@/stores/auth.js', () => ({ useAuthStore: () => ({ user: { studentId: 'S1' } }) }))
vi.mock('@/stores/workflow.js', () => ({
  useWorkflowStore: () => ({
    get score() {
      return state.score
    },
    loadCurrentScore: state.load
  })
}))
vi.mock('@/services/workflowApi.js', () => ({ default: { getScoreSource: state.detail } }))
import Statistics from '../src/pages/student/statistics/Statistics.vue'
beforeEach(() => {
  vi.clearAllMocks()
  state.score = {
    year: 2028,
    snapshot_version: 1,
    status: 'current',
    updated_at: '2026-11-19T10:34:21.510553Z',
    rule_version_ids: [-1],
    rule_versions: [{ reference: -1, label: '学业竞赛计分规则（第3版）' }],
    formula: 'academic_score * academic_weight / 100 + academic + comprehensive',
    base: { academic_score: '76.0000' },
    categories: {
      academic: { effective_score: '1.6667' },
      comprehensive: { effective_score: '0.0000' }
    },
    comprehensive_score: '62.4667',
    entries: [
      {
        id: 1,
        project_source: {
          type: 'material',
          id: '1',
          category: 'competition',
          name: '蓝桥杯竞赛获奖'
        },
        rule_label: '学业竞赛计分规则（第3版）',
        scoring_status: 'scored',
        candidate_score: '1.6667',
        included_score: '1.6667',
        included: true,
        updated_at: '2026-11-19T10:34:21.492430Z',
        allowed_actions: []
      }
    ]
  }
  state.detail.mockResolvedValue({
    title: '蓝桥杯竞赛获奖',
    status: 'scored',
    data: { project_name: '蓝桥杯', award: 'second' },
    attachments: [
      { id: 1, filename: 'proof.png', url: '/api/materials/competition/records/1/attachments/1' }
    ],
    ocr_raw_terms: { fields: { award: '二等奖' } },
    history: [
      { id: 1, action: 'competition_approved', comment: '', created_at: '2026-11-19T10:34:21Z' }
    ]
  })
  state.load.mockResolvedValue({})
})
test('student statistics renders project names, Chinese rule/formula/status and readable Beijing times', async () => {
  const w = mount(Statistics)
  await flushPromises()
  expect(state.load).toHaveBeenCalledWith('S1')
  const text = w.text()
  for (const value of [
    '蓝桥杯竞赛获奖',
    '当前有效',
    '学业竞赛计分规则（第3版）',
    '学业基础分 × 学业成绩权重 ÷ 100 + 学术专长计入分 + 综合表现计入分',
    '2026年11月19日 18:34:21',
    '62.4667',
    '已计分'
  ])
    expect(text).toContain(value)
  for (const raw of ['competition', 'material #', 'current', '-1', 'academic_score', '2026-11-19T'])
    expect(text).not.toContain(raw)
  expect(w.findAll('tbody tr')).toHaveLength(1)
  expect(w.get('.score-details-button').text()).toBe('查看详情')
  expect(w.get('.score-main-value strong').text()).toBe('62.4667')
  expect(w.findAll('.score-components>div')).toHaveLength(3)
  w.unmount()
})
test('missing project metadata stays a Chinese description rather than internal source codes', async () => {
  delete state.score.entries[0].project_source.name
  const w = mount(Statistics)
  await flushPromises()
  expect(w.text()).toContain('学业竞赛材料（编号1）')
  expect(w.text()).not.toContain('competition')
  w.unmount()
})

test('opens the actual project details from a score row and supports closing and image enlargement', async () => {
  const w = mount(Statistics, { attachTo: document.body })
  await flushPromises()
  const trigger = w.get('.score-details-button')
  await trigger.trigger('click')
  await flushPromises()
  expect(state.detail).toHaveBeenCalledWith('S1', 2028, 'material', '1', expect.any(AbortSignal))
  let dialog = document.querySelector('[aria-label="证明原件大图预览"]')
  expect(dialog).toBeNull()
  const source = document.querySelector('[aria-labelledby="score-source-title"]')
  expect(source.textContent).toContain('申报信息')
  expect(source.textContent).toContain('审核通过并计分')
  expect(source.textContent).toContain('蓝桥杯')
  source.querySelector('.thumbnail').click()
  await flushPromises()
  dialog = document.querySelector('[aria-label="证明原件大图预览"]')
  expect(dialog).not.toBeNull()
  expect(dialog.querySelector('img').getAttribute('src')).toContain('inline=1')
  dialog.querySelector('button').click()
  await flushPromises()
  source.querySelector('.source-close').click()
  await flushPromises()
  expect(document.querySelector('[aria-labelledby="score-source-title"]')).toBeNull()
  expect(document.activeElement).toBe(trigger.element)
  w.unmount()
})

test('loads details on demand, exposes retry for failures and rejects unavailable sources cleanly', async () => {
  state.detail.mockRejectedValueOnce(Object.assign(new Error('不可用'), { status: 404 }))
  const w = mount(Statistics, { attachTo: document.body })
  await flushPromises()
  expect(state.detail).not.toHaveBeenCalled()
  await w.get('.score-details-button').trigger('click')
  await flushPromises()
  expect(document.querySelector('[role=alert]').textContent).toContain('原记录暂不可用')
  document.querySelector('.source-retry').click()
  await flushPromises()
  expect(state.detail).toHaveBeenCalledTimes(2)
  expect(document.querySelector('.source-section').textContent).toContain('蓝桥杯')
  w.unmount()
  expect(document.body.style.overflow).toBe('')
})

test('detail loading and permissions remain actionable and closing during a request cancels it', async () => {
  state.detail.mockReturnValue(new Promise(() => {}))
  const w = mount(Statistics, { attachTo: document.body })
  await flushPromises()
  await w.get('.score-details-button').trigger('click')
  await flushPromises()
  expect(document.querySelector('.source-dialog-body [role=status]').textContent).toContain(
    '正在加载'
  )
  const signal = state.detail.mock.calls[0][4]
  document.querySelector('.source-close').click()
  await flushPromises()
  expect(signal.aborted).toBe(true)
  w.unmount()
  state.detail.mockRejectedValue(Object.assign(new Error('forbidden'), { status: 403 }))
  const denied = mount(Statistics, { attachTo: document.body })
  await flushPromises()
  await denied.get('.score-details-button').trigger('click')
  await flushPromises()
  expect(document.querySelector('[role=alert]').textContent).toContain('没有访问此项目详情的权限')
  denied.unmount()
})

test('nested image and detail dialogs release the shared scroll lock when leaving the page', async () => {
  const w = mount(Statistics, { attachTo: document.body })
  await flushPromises()
  await w.get('.score-details-button').trigger('click')
  await flushPromises()
  document.querySelector('.thumbnail').click()
  await flushPromises()
  expect(document.body.style.overflow).toBe('hidden')
  w.unmount()
  await flushPromises()
  expect(document.body.style.overflow).toBe('')
})

test('shows the paper bonus separately from the capped academic group', async () => {
  Object.assign(state.score.entries[0], {
    project_source: { type: 'material', id: '4', category: 'research_paper' },
    candidate_score: '20.0000', item_bonus: '20.0000'
  })
  state.score.categories.academic = { effective_score: '15.0000', note: '最终实际计分受本组上限影响。' }
  const w = mount(Statistics, { attachTo: document.body })
  await flushPromises()
  expect(w.get('.included-score').text()).toBe('20.0000')
  expect(w.get('.score-components').text()).toContain('学术专长最终实际计分15.0000')
  expect(w.get('small.score-cap-note').text()).toContain('受本组上限影响')
  await w.get('.score-details-button').trigger('click')
  await flushPromises()
  expect(document.querySelector('.source-score-summary').textContent).toContain('逐项加分20.0000')
  w.unmount()
})
