// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  api: {
    getCompetitionWorkbenchSummary: vi.fn(),
    getTeacherCompetitionSummary: vi.fn()
  }
}))

vi.mock('@/services/materialApi.js', () => ({ default: state.api }))

import TeacherStudentSummary from '../src/pages/teacher/students/TeacherStudentSummary.vue'

const SUMMARY = {
  student_id: 'student001',
  year: 2028,
  aggregate: {
    cycle_code: 2028,
    record_count: 3,
    status_counts: { scored: 2, needs_correction: 1 },
    pending_count: 0,
    included_count: 2,
    excluded_count: 0,
    total_candidate_score: '15.0000',
    total_effective_score: '15.0000'
  },
  capabilities: { editable: false, mergeable: false, score_override: false },
  items: [
    {
      record_id: 1,
      project_name: '基于大模型的推免材料智能审核系统',
      competition_id: 'c01-china-college-student-innovation',
      level: 'national',
      award: 'first_or_above',
      award_date: '2026-06-15',
      event_year: 2026,
      status: 'scored',
      candidate_score: '10.0000',
      effective_score: '10.0000',
      included: true,
      exclusion_reason: null,
      attachments: [{ id: 1, filename: 'proof_0.png', url: '/api/materials/competition/records/1/attachments/1' }]
    },
    {
      record_id: 3,
      project_name: '校园二手书交易平台',
      competition_id: 'c03-challenge-cup-business-plan',
      level: 'national',
      award: 'third',
      award_date: '2027-06-15',
      event_year: 2027,
      status: 'needs_correction',
      candidate_score: '3.3333',
      effective_score: null,
      included: null,
      exclusion_reason: null,
      attachments: []
    }
  ]
}

function workbench(students = ['student001']) {
  return {
    cycle_code: 2028,
    pending_count: 0,
    items: students.map((id) => ({ id: 1, student_id: id, status: 'submitted', version: 2 })),
    reviewed_items: []
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  state.api.getCompetitionWorkbenchSummary.mockResolvedValue(workbench())
  state.api.getTeacherCompetitionSummary.mockResolvedValue(SUMMARY)
})

describe('教师·学生竞赛计分汇总', () => {
  it('默认周期取后端当前周期，而不是浏览器本地年份', async () => {
    const wrapper = mount(TeacherStudentSummary)
    await flushPromises()

    const yearInput = wrapper.findAll('input')[1]
    expect(yearInput.element.value).toBe('2028')
    // 2026 是浏览器当前年份；默认值绝不能落在这里，否则永远查不到数据。
    expect(Number(yearInput.element.value)).not.toBe(new Date().getFullYear())
  })

  it('唯一候选学生时自动查询，并带上后端周期', async () => {
    mount(TeacherStudentSummary)
    await flushPromises()

    expect(state.api.getTeacherCompetitionSummary).toHaveBeenCalledWith('student001', 2028)
  })

  it('渲染合计卡片与中文状态，不计入项不显示计入分', async () => {
    const wrapper = mount(TeacherStudentSummary)
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('计入分合计')
    expect(text).toContain('15.0000')
    expect(text).toContain('已计分')
    expect(text).toContain('待补正')
    expect(text).toContain('国家级')
    expect(text).toContain('一等奖及以上')
    // 被退回的材料没有计入分，必须显示占位而不是 0
    expect(text).toContain('审核退回，待学生补正')
  })

  it('无材料时给出可解释的空状态', async () => {
    state.api.getTeacherCompetitionSummary.mockResolvedValue({
      student_id: 'student001',
      year: 2028,
      aggregate: { record_count: 0, included_count: 0, excluded_count: 0, pending_count: 0 },
      items: []
    })
    const wrapper = mount(TeacherStudentSummary)
    await flushPromises()

    expect(wrapper.text()).toContain('没有竞赛材料记录')
  })

  it('学号为空时不发请求，并给出校验提示', async () => {
    state.api.getCompetitionWorkbenchSummary.mockResolvedValue(workbench(['a001', 'b002']))
    const wrapper = mount(TeacherStudentSummary)
    await flushPromises()

    const form = wrapper.find('form')
    await form.trigger('submit')
    await flushPromises()

    expect(state.api.getTeacherCompetitionSummary).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('请填写学生学号')
  })

  it('接口失败时展示可操作错误与重试按钮', async () => {
    state.api.getTeacherCompetitionSummary.mockRejectedValue(new Error('后端不可用'))
    const wrapper = mount(TeacherStudentSummary)
    await flushPromises()

    expect(wrapper.text()).toContain('后端不可用')
    expect(wrapper.text()).toContain('重新加载')
  })
})

it('previews original attachments in a dialog and reports an unavailable file', async () => {
  state.api.getTeacherCompetitionSummary.mockResolvedValue({
    ...SUMMARY,
    items: [{
      ...SUMMARY.items[0],
      attachments: [
        ...SUMMARY.items[0].attachments,
        { id: 2, filename: '第二份.pdf', url: '/api/materials/competition/records/1/attachments/2' }
      ]
    }]
  })
  const fetchAttachment = vi.fn()
    .mockResolvedValueOnce({ ok: true, blob: async () => new Blob(['image'], { type: 'image/png' }) })
    .mockResolvedValueOnce({ ok: false })
  vi.stubGlobal('fetch', fetchAttachment)
  const wrapper = mount(TeacherStudentSummary, { attachTo: document.body })
  try {
    await flushPromises()
    const trigger = wrapper.findAll('button').find((button) => button.text().startsWith('查看原件'))
    await trigger.trigger('click')
    await flushPromises()
    expect(wrapper.get('dialog').element.open).toBe(true)
    expect(wrapper.get('dialog img').attributes('alt')).toBe('proof_0.png')
    expect(fetchAttachment.mock.calls[0][0].searchParams.get('inline')).toBe('1')
    await wrapper.get('dialog select').setValue('1')
    await flushPromises()
    expect(wrapper.get('dialog [role=alert]').text()).toContain('原件无法预览')
    await wrapper.get('dialog button').trigger('click')
    await wrapper.get('dialog').trigger('close')
    expect(wrapper.get('dialog').element.open).toBe(false)
    expect(document.activeElement).toBe(trigger.element)
  } finally {
    wrapper.unmount()
    vi.unstubAllGlobals()
  }
})


it('renders the same-event exclusion in Chinese while preserving the zero included score', async () => {
  const response = structuredClone(SUMMARY)
  response.items[0].included = false
  response.items[0].effective_score = '0.0000'
  response.items[0].exclusion_reason = 'same_event_lower_score'
  state.api.getTeacherCompetitionSummary.mockResolvedValue(response)
  const w = mount(TeacherStudentSummary)
  try {
    await flushPromises()
    expect(w.text()).toContain('同一赛事同年度仅计最高分')
    expect(w.text()).not.toContain('same_event_lower_score')
    expect(w.get('tbody tr').text()).toContain('0.0000')
  } finally { w.unmount() }
})
