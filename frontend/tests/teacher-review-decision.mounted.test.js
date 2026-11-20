// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  api: {
    getCompetitionWorkbenchSummary: vi.fn(),
    getCompetitionReviewContext: vi.fn(),
    getTeacherCompetitionSummary: vi.fn(),
    reviewCompetition: vi.fn()
  }
}))

vi.mock('@/services/materialApi.js', () => ({ default: state.api }))

import TeacherCompetitionReview from '../src/pages/teacher/reviews/TeacherCompetitionReview.vue'

function reviewPayload(decision, comment) {
  return {
    decision,
    comment,
    actor: { id: 2, name: '演示教师', username: 'teacher001', role: 'teacher' },
    at: '2026-11-20T05:15:09.929823Z'
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  state.api.getCompetitionWorkbenchSummary.mockResolvedValue({
    cycle_code: 2028,
    pending_count: 0,
    items: [],
    reviewed_items: [
      {
        id: 1,
        student_id: 'student001',
        status: 'scored',
        version: 5,
        project_name: '已通过作品',
        review: reviewPayload('approve', '材料与原件一致')
      },
      {
        id: 3,
        student_id: 'student001',
        status: 'needs_correction',
        version: 5,
        project_name: '被退回作品',
        review: reviewPayload('return', '请补充赛事级别证明')
      }
    ]
  })
  state.api.getCompetitionReviewContext.mockResolvedValue({
    record_id: 1,
    material_version: 4,
    attachments: [
      {
        id: 2,
        filename: 'proof.png',
        media_type: 'image/png',
        url: '/proof',
        preview_url: '/proof?inline=1'
      }
    ],
    confirmed_terms: { project_name: '已通过作品' },
    ocr_raw_terms: {},
    candidate_score: '10.0000',
    rule_basis: { competition_name: '中国国际大学生创新大赛', category: 'A+', package_version: 1 },
    history: [
      {
        action: 'submitted',
        comment: null,
        actor: { name: '演示同学', role: 'student' },
        created_at: '2026-11-20T05:15:09.044690Z'
      },
      {
        action: 'competition_approved',
        comment: '材料与原件一致',
        actor: { name: '演示教师', role: 'teacher' },
        created_at: '2026-11-20T05:15:09.929823Z'
      }
    ],
    allowed_actions: []
  })
})

describe('教师·竞赛审核记录的可读性', () => {
  it('审核记录卡片直接显示通过/退回、审核人与意见', async () => {
    const wrapper = mount(TeacherCompetitionReview, { props: { mode: 'history' } })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('已通过')
    expect(text).toContain('已退回')
    expect(text).toContain('演示教师')
    expect(text).toContain('材料与原件一致')
    expect(text).toContain('请补充赛事级别证明')
    // 状态徽章必须是中文，不能把状态码直接糊给教师
    expect(text).toContain('已计分')
    expect(text).not.toContain('competition_approved')
    expect(text).not.toContain('needs_correction')
  })

  it('审核轨迹显示中文动作、审核人与北京时间', async () => {
    const wrapper = mount(TeacherCompetitionReview, { props: { mode: 'history' } })
    await flushPromises()
    await wrapper.get('.pending-card button').trigger('click')
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('提交审核')
    expect(text).toContain('审核通过')
    expect(text).toContain('演示教师')
    expect(text).toContain('演示同学')
    // 后端给的是 UTC，界面必须转成北京时间；05:15Z = 13:15
    expect(text).toContain('13:15:09')
    expect(text).not.toContain('competition_approved')
  })
})
