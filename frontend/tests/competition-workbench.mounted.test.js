// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  api: {
    getCompetitionWorkbenchSummary: vi.fn(),
    getCompetitionReviewContext: vi.fn(),
    getTeacherCompetitionSummary: vi.fn(),
    reviewCompetition: vi.fn()
  },
  applications: []
}))
vi.mock('@/services/materialApi.js', () => ({ default: state.api }))
vi.mock('@/stores/auth.js', () => ({
  useAuthStore: () => ({
    userName: '测试用户',
    user: { username: 'student001', student_id: 'student001' }
  })
}))
vi.mock('@/stores/applications.js', () => ({
  useApplicationsStore: () => ({
    applications: state.applications,
    pendingApplications: state.applications.filter((item) => item.status === 'pending'),
    loading: false,
    error: null,
    fetchApplications: vi.fn()
  })
}))

import StudentHome from '../src/pages/student/home/Home.vue'
import RoleHome from '../src/components/common/RoleHome.vue'
import TeacherCompetitionReview from '../src/pages/teacher/reviews/TeacherCompetitionReview.vue'

beforeEach(() => {
  vi.clearAllMocks()
  state.applications.length = 0
  state.api.getCompetitionWorkbenchSummary.mockResolvedValue({
    cycle_code: 2028,
    pending_count: 1,
    needs_correction_count: 0,
    completed_count: 0,
    items: [
      { id: 1, student_id: 'student001', status: 'submitted', version: 3, project_name: '竞赛作品' }
    ],
    reviewed_items: [
      { id: 2, student_id: 'student001', status: 'scored', version: 5, project_name: '已通过作品' }
    ]
  })
  state.api.getCompetitionReviewContext.mockResolvedValue({
    record_id: 1,
    material_version: 3,
    attachments: [
      {
        id: 2,
        filename: 'proof.jpg',
        media_type: 'image/jpeg',
        url: '/proof',
        preview_url: '/proof?inline=1'
      }
    ],
    confirmed_terms: { project_name: '竞赛作品' },
    ocr_raw_terms: {},
    candidate_score: 3.333,
    rule_basis: { competition_name: '计算机设计大赛', category: 'A-', package_version: 1 },
    history: [{ action: 'submitted', comment: '首次提交', created_at: '2026-11-11T10:00:00' }],
    allowed_actions: ['approve', 'return']
  })
  state.api.reviewCompetition.mockResolvedValue({ status: 'needs_correction', replayed: false })
})

describe('authoritative competition workbench projection', () => {
  it('shows student competition counts separately from legacy Application data', async () => {
    const wrapper = mount(StudentHome, {
      global: {
        stubs: {
          WelcomeHeader: true,
          WorkbenchAction: {
            template: '<div><slot name="description"/><slot name="action"/></div>'
          },
          ApplicationPeriodPanel: true
        }
      }
    })
    await flushPromises()
    const panel = wrapper.get('[aria-label="竞赛新链路进度"]')
    expect(panel.text()).toContain('1份')
    expect(panel.text()).toContain('MaterialRecord 权威状态')
  })

  it('includes competition corrections in the main student action card and routes to materials', async () => {
    state.api.getCompetitionWorkbenchSummary.mockResolvedValueOnce({
      cycle_code: 2028,
      pending_count: 0,
      needs_correction_count: 1,
      completed_count: 0,
      items: []
    })
    const wrapper = mount(StudentHome, {
      global: {
        stubs: {
          WelcomeHeader: true,
          WorkbenchAction: {
            template: '<div><slot name="description"/><slot name="action"/></div>'
          },
          ApplicationPeriodPanel: true
        }
      }
    })
    await flushPromises()
    expect(wrapper.text()).toContain('1 份待修改')
    await wrapper.get('.workbench-primary').trigger('click')
    expect(wrapper.emitted('navigate').at(-1)).toEqual(['materials'])
  })

  it('shows teacher competition pending count separately from compatibility applications', async () => {
    state.applications.push(
      { status: 'pending', rule: { sub_type: 'competition' } },
      { status: 'pending', rule: { sub_type: 'honor' } }
    )
    const wrapper = mount(RoleHome, {
      props: { role: 'teacher' },
      global: {
        stubs: {
          WelcomeHeader: true,
          WorkbenchAction: {
            template: '<div><slot name="description"/><slot name="action"/></div>'
          },
          ApplicationPeriodPanel: true
        }
      }
    })
    await flushPromises()
    expect(wrapper.text()).toContain('1 份竞赛材料待审核')
    expect(wrapper.text()).toContain('1 份非竞赛兼容申请')
  })

  it('renders student summary loading and actionable error states', async () => {
    state.api.getCompetitionWorkbenchSummary.mockReturnValueOnce(new Promise(() => {}))
    const loading = mount(StudentHome, {
      global: {
        stubs: { WelcomeHeader: true, WorkbenchAction: true, ApplicationPeriodPanel: true }
      }
    })
    expect(loading.get('[aria-label="竞赛新链路进度"] [role="status"]').text()).toContain(
      '正在读取'
    )
    loading.unmount()

    state.api.getCompetitionWorkbenchSummary.mockRejectedValueOnce(new Error('竞赛摘要服务不可用'))
    const failed = mount(StudentHome, {
      global: {
        stubs: { WelcomeHeader: true, WorkbenchAction: true, ApplicationPeriodPanel: true }
      }
    })
    await flushPromises()
    expect(failed.get('[aria-label="竞赛新链路进度"] [role="alert"]').text()).toContain(
      '服务不可用'
    )
  })

  it('renders pending, read-only facts and authority-driven review actions', async () => {
    const wrapper = mount(TeacherCompetitionReview)
    await flushPromises()
    expect(wrapper.text()).toContain('1份待审核')
    expect(wrapper.text()).toContain('竞赛作品')
    await wrapper.get('.pending-card button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('证明原件')
    const preview = wrapper.get('.evidence-file img')
    expect(preview.attributes('src')).toBe('/proof?inline=1')
    expect(preview.attributes('alt')).toContain('proof.jpg')
    expect(wrapper.get('.evidence-file a').text()).toBe('下载原件')
    expect(wrapper.text()).toContain('后端候选分 3.333')
    expect(wrapper.text()).toContain('历史意见与状态')
    expect(wrapper.text()).toContain('首次提交')
    expect(wrapper.text()).toContain('退回修改')
    expect(wrapper.text()).toContain('审核通过')
    await wrapper.get('#review-comment').setValue('请修改后重提')
    await wrapper
      .findAll('.review-dialog footer button')
      .find((button) => button.text().includes('退回修改'))
      .trigger('click')
    await flushPromises()
    expect(state.api.reviewCompetition).toHaveBeenCalledWith(
      1,
      3,
      'return',
      '请修改后重提',
      expect.any(String),
      undefined
    )

    const approve = mount(TeacherCompetitionReview)
    await flushPromises()
    await approve.get('.pending-card button').trigger('click')
    await flushPromises()
    await approve.get('#review-comment').setValue('材料核验通过')
    await approve
      .findAll('.review-dialog footer button')
      .find((button) => button.text().includes('审核通过'))
      .trigger('click')
    await flushPromises()
    expect(state.api.reviewCompetition).toHaveBeenCalledWith(
      1,
      3,
      'approve',
      '材料核验通过',
      expect.any(String),
      undefined
    )
  })

  it('requires a reason when returning material and focuses the field', async () => {
    const wrapper = mount(TeacherCompetitionReview, { attachTo: document.body })
    await flushPromises()
    await wrapper.get('.pending-card button').trigger('click')
    await flushPromises()
    await wrapper
      .findAll('.review-dialog footer button')
      .find((button) => button.text().includes('退回修改'))
      .trigger('click')
    await flushPromises()

    expect(wrapper.get('#review-comment-error').text()).toContain('退回修改时，请填写具体原因')
    expect(wrapper.get('#review-comment').attributes('aria-invalid')).toBe('true')
    expect(wrapper.get('#review-comment').element).toBe(document.activeElement)
    expect(state.api.reviewCompetition).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('renders permission errors and processed records without review controls', async () => {
    state.api.getCompetitionWorkbenchSummary.mockRejectedValueOnce(
      Object.assign(new Error('没有权限'), { status: 403 })
    )
    const denied = mount(TeacherCompetitionReview)
    await flushPromises()
    expect(denied.get('[role="alert"]').text()).toContain('没有权限')
    denied.unmount()

    state.api.getCompetitionReviewContext.mockResolvedValueOnce({
      record_id: 1,
      material_version: 4,
      attachments: [],
      confirmed_terms: {},
      ocr_raw_terms: {},
      candidate_score: 3.333,
      rule_basis: { competition_name: '计算机设计大赛', category: 'A-', package_version: 1 },
      allowed_actions: [],
      history: []
    })
    const processed = mount(TeacherCompetitionReview)
    await flushPromises()
    await processed.get('.pending-card button').trigger('click')
    await flushPromises()
    expect(processed.text()).toContain('当前不可处理')
    expect(processed.findAll('button').some((b) => b.text() === '审核通过')).toBe(false)
  })

  it('renders a successful empty teacher workbench', async () => {
    state.api.getCompetitionWorkbenchSummary.mockResolvedValueOnce({
      cycle_code: 2028,
      pending_count: 0,
      items: []
    })
    const wrapper = mount(TeacherCompetitionReview)
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toContain('没有待审核竞赛材料')
  })

  it('renders processed competition materials as read-only history', async () => {
    state.api.getCompetitionReviewContext.mockResolvedValueOnce({
      record_id: 2,
      material_version: 5,
      attachments: [],
      confirmed_terms: { project_name: '已通过作品' },
      ocr_raw_terms: {},
      candidate_score: 3.333,
      rule_basis: { competition_name: '计算机设计大赛', category: 'A-', package_version: 1 },
      allowed_actions: [],
      history: [{ action: 'approved', comment: '材料核验通过', created_at: '2026-11-11T12:00:00' }]
    })
    const wrapper = mount(TeacherCompetitionReview, { props: { mode: 'history' } })
    await flushPromises()
    expect(wrapper.text()).toContain('竞赛审核记录')
    expect(wrapper.text()).toContain('已通过作品')
    expect(wrapper.text()).not.toContain('竞赛作品')
    await wrapper.get('.pending-card button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('材料核验通过')
    expect(wrapper.text()).toContain('该材料当前不可处理')
    expect(wrapper.findAll('button').some((b) => b.text() === '审核通过')).toBe(false)
  })
})

it('requires explicit manual OCR confirmation before teacher approves', async () => {
  state.api.getCompetitionReviewContext.mockResolvedValue({
    record_id: 1,
    material_version: 3,
    attachments: [],
    confirmed_terms: { project_name: '作品' },
    ocr_raw_terms: {},
    candidate_score: 3.33,
    rule_basis: { competition_name: '比赛', category: 'A', package_version: 1 },
    allowed_actions: ['approve', 'return'],
    ocr_assessment: {
      declared_estimate: '3.33',
      review_mode: 'manual_confirmation',
      job: { status: 'completed' },
      missing_fields: ['level'],
      differences: []
    }
  })
  const w = mount(TeacherCompetitionReview)
  await flushPromises()
  await w
    .findAll('button')
    .find((b) => b.text() === '核对材料')
    .trigger('click')
  await flushPromises()
  await w.get('textarea').setValue('核对原件与申报分数')
  await w
    .findAll('button')
    .find((b) => b.text() === '审核通过')
    .trigger('click')
  await flushPromises()
  expect(state.api.reviewCompetition).not.toHaveBeenCalled()
  expect(w.text()).toContain('请先人工核对')
  await w.get('input[type=checkbox]').setValue(true)
  await w
    .findAll('button')
    .find((b) => b.text() === '审核通过')
    .trigger('click')
  await flushPromises()
  expect(state.api.reviewCompetition.mock.calls[0].at(-1)).toBe(true)
  w.unmount()
})

it('approves without requiring review text', async () => {
  const w = mount(TeacherCompetitionReview)
  await flushPromises()
  await w.get('.pending-card button').trigger('click')
  await flushPromises()
  expect(w.get('#review-comment').attributes('required')).toBeUndefined()
  await w
    .findAll('.review-dialog footer button')
    .find((b) => b.text() === '审核通过')
    .trigger('click')
  await flushPromises()
  expect(state.api.reviewCompetition).toHaveBeenCalledWith(
    1,
    3,
    'approve',
    '',
    expect.any(String),
    undefined
  )
  w.unmount()
})
