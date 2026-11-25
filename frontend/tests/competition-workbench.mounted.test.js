// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  api: {
    getCompetitionWorkbenchSummary: vi.fn(),
    getStudentMaterialSummary: vi.fn(),
    getCompetitionReviewContext: vi.fn(),
    getTeacherCompetitionSummary: vi.fn(),
    getTeacherMaterialSummary: vi.fn(),
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
import ManualMaterialReview from '../src/components/common/ManualMaterialReview.vue'
import PendingReview from '../src/pages/teacher/reviews/PendingReview.vue'
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
  state.api.getStudentMaterialSummary.mockResolvedValue({
    approved_count: 0,
    pending_count: 1,
    needs_correction_count: 0,
    rejected_count: 0,
    submitted_count: 1
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
  state.api.getTeacherMaterialSummary.mockResolvedValue({ pending_count: 0 })
})

describe('authoritative competition workbench projection', () => {
  it('shows one unified MaterialRecord summary on the student home', async () => {
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
    const panel = wrapper.get('[aria-label="材料审核进度"]')
    expect(panel.text()).toContain('已提交 1 份材料')
    expect(wrapper.find('[aria-label="竞赛新链路进度"]').exists()).toBe(false)
  })

  it('includes material corrections in the main student action card and routes to history', async () => {
    state.api.getStudentMaterialSummary.mockResolvedValueOnce({
      approved_count: 0,
      pending_count: 0,
      needs_correction_count: 1,
      rejected_count: 0,
      submitted_count: 1
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
    expect(wrapper.emitted('navigate').at(-1)).toEqual(['application-record'])
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
    expect(wrapper.text()).toContain('1份材料待审核')
    expect(wrapper.text()).not.toContain('非竞赛材料待审核')
  })

  it('renders student summary loading and actionable error states', async () => {
    state.api.getStudentMaterialSummary.mockReturnValueOnce(new Promise(() => {}))
    const loading = mount(StudentHome, {
      global: {
        stubs: { WelcomeHeader: true, WorkbenchAction: true, ApplicationPeriodPanel: true }
      }
    })
    expect(loading.get('[aria-label="材料审核进度"] [role="status"]').text()).toContain(
      '正在加载'
    )
    loading.unmount()

    state.api.getStudentMaterialSummary.mockRejectedValueOnce(new Error('材料摘要服务不可用'))
    const failed = mount(StudentHome, {
      global: {
        stubs: { WelcomeHeader: true, WorkbenchAction: true, ApplicationPeriodPanel: true }
      }
    })
    await flushPromises()
    expect(failed.get('[aria-label="材料审核进度"] [role="alert"]').text()).toContain(
      '服务不可用'
    )
  })

  it('renders pending, read-only facts and authority-driven review actions', async () => {
    const wrapper = mount(TeacherCompetitionReview)
    await flushPromises()
    expect(wrapper.text()).not.toContain('竞赛材料待审工作台')
    expect(wrapper.text()).not.toContain('授权学生汇总')
    expect(wrapper.text()).toContain('竞赛作品')
    expect(wrapper.get('.material-review-card > h3').text()).toBe('学生 student001 · 材料 #1')
    expect(wrapper.text()).toContain('证明原件')
    const preview = wrapper.get('.review-evidence-grid .thumbnail img')
    expect(preview.attributes('src')).toBe('/proof?inline=1')
    expect(preview.attributes('alt')).toContain('proof.jpg')
    expect(wrapper.get('.review-evidence-grid .attachment-downloads a').text()).toBe('下载原件')
    const details = wrapper.get('.competition-review-details')
    expect(details.element.open).toBe(false)
    expect(details.get('summary').text()).toBe('计分依据与 OCR 详情')
    details.element.open = true
    expect(details.text()).toContain('后端候选分 3.333')
    expect(wrapper.get('.material-review-actions').findAll('button').map(button => button.text()))
      .toEqual(['核验通过', '退回补充'])
    expect(wrapper.text()).toContain('历史意见与状态')
    expect(wrapper.text()).toContain('首次提交')
    expect(wrapper.text()).toContain('退回补充')
    expect(wrapper.text()).toContain('核验通过')
    await wrapper.get('#review-comment-1').setValue('请修改后重提')
    await wrapper
      .findAll('.competition-evidence .material-review-actions button')
      .find((button) => button.text().includes('退回补充'))
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
    await approve.get('#review-comment-1').setValue('材料核验通过')
    await approve
      .findAll('.competition-evidence .material-review-actions button')
      .find((button) => button.text().includes('核验通过'))
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
    await wrapper
      .findAll('.competition-evidence .material-review-actions button')
      .find((button) => button.text().includes('退回补充'))
      .trigger('click')
    await flushPromises()

    expect(wrapper.get('#review-comment-1-error').text()).toContain('退回修改时，请填写具体原因')
    expect(wrapper.get('#review-comment-1').attributes('aria-invalid')).toBe('true')
    expect(wrapper.get('#review-comment-1').element).toBe(document.activeElement)
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
    expect(processed.text()).toContain('当前不可处理')
    expect(processed.findAll('button').some((b) => b.text() === '核验通过')).toBe(false)
  })

  it('renders a successful empty teacher workbench', async () => {
    state.api.getCompetitionWorkbenchSummary.mockResolvedValueOnce({
      cycle_code: 2028,
      pending_count: 0,
      items: []
    })
    const wrapper = mount(TeacherCompetitionReview)
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toContain('当前类别暂无待核验材料。')
  })

  it('reloads review history with the submitted student ID and restores the default when cleared', async () => {
    const wrapper = mount(TeacherCompetitionReview, {
      props: { mode: 'history', keyword: '' }
    })
    await flushPromises()
    await wrapper.setProps({ keyword: 'student001' })
    await flushPromises()
    expect(state.api.getCompetitionWorkbenchSummary).toHaveBeenLastCalledWith(undefined, undefined, { keyword: 'student001' })
    await wrapper.setProps({ keyword: '' })
    await flushPromises()
    expect(state.api.getCompetitionWorkbenchSummary).toHaveBeenLastCalledWith(undefined, undefined, { keyword: '' })
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
    expect(wrapper.findAll('button').some((b) => b.text() === '核验通过')).toBe(false)
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
  await w.get('textarea').setValue('核对原件与申报分数')
  await w
    .findAll('button')
    .find((b) => b.text() === '核验通过')
    .trigger('click')
  await flushPromises()
  expect(state.api.reviewCompetition).not.toHaveBeenCalled()
  expect(w.text()).toContain('请先人工核对')
  await w.get('input[type=checkbox]').setValue(true)
  await w
    .findAll('button')
    .find((b) => b.text() === '核验通过')
    .trigger('click')
  await flushPromises()
  expect(state.api.reviewCompetition.mock.calls[0].at(-1)).toBe(true)
  w.unmount()
})

it('approves without requiring review text', async () => {
  const w = mount(TeacherCompetitionReview)
  await flushPromises()
  expect(w.get('#review-comment-1').attributes('required')).toBeUndefined()
  await w
    .findAll('.competition-evidence .material-review-actions button')
    .find((b) => b.text() === '核验通过')
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

it('filters existing history cards and restores them when the search is cleared', async () => {
  const workbench = await state.api.getCompetitionWorkbenchSummary()
  workbench.reviewed_items = [
    ...workbench.reviewed_items,
    ...['scored', 'needs_correction', 'needs_correction'].map((status, index) => ({
      id: 10 + index, student_id: 'sample2612', status, version: 4,
      project_name: `审核样本 ${index}`,
      review: { decision: status === 'scored' ? 'approve' : 'return', comment: '审核意见样本' }
    }))
  ]
  state.api.getCompetitionWorkbenchSummary.mockImplementation(async (_signal, _studentId, options) => ({
    ...workbench,
    reviewed_items: workbench.reviewed_items.filter(row =>
      !options?.keyword || row.student_id.endsWith(options.keyword)
    )
  }))
  const wrapper = mount(TeacherCompetitionReview, { props: { mode: 'history' } })
  await flushPromises()
  expect(wrapper.findAll('.pending-card')).toHaveLength(4)
  await wrapper.setProps({ keyword: '2612' })
  await flushPromises()
  expect(state.api.getCompetitionWorkbenchSummary).toHaveBeenLastCalledWith(undefined, undefined, { keyword: '2612' })
  expect(state.api.getTeacherCompetitionSummary).not.toHaveBeenCalled()
  expect(wrapper.findAll('.pending-card')).toHaveLength(3)
  expect(wrapper.text()).toContain('审核意见样本')
  expect(wrapper.text()).not.toContain('已通过作品')
  expect(wrapper.text()).not.toContain('竞赛作品')
  expect(wrapper.find('table').exists()).toBe(false)
  await wrapper.get('.pending-card button').trigger('click')
  await flushPromises()
  expect(state.api.getCompetitionReviewContext).toHaveBeenCalledWith(10)
  const buttons = wrapper.get('dialog').findAll('button').map((button) => button.text())
  expect(buttons).not.toContain('核验通过')
  expect(buttons).not.toContain('退回补充')
  await wrapper.setProps({ keyword: 'missing-student' })
  await flushPromises()
  expect(wrapper.findAll('.pending-card')).toHaveLength(0)
  expect(wrapper.text()).toContain('暂无匹配的竞赛审核记录。')
  await wrapper.setProps({ keyword: '' })
  await flushPromises()
  expect(wrapper.findAll('.pending-card')).toHaveLength(4)
  wrapper.unmount()
})

it('keeps each history search scoped to its own group', async () => {
  const wrapper = mount(PendingReview, {
    props: { history: true },
    global: { stubs: { ManualMaterialReview: true, TeacherCompetitionReview: true } }
  })
  expect(wrapper.find('#review-history-student').exists()).toBe(false)
  const groups = wrapper.findAll('details')
  expect(groups).toHaveLength(5)
  for (const group of groups) {
    const input = group.get('input[type="search"]')
    await input.setValue('student001')
    await group.get('form').trigger('submit')
    expect(group.findAll('manual-material-review-stub').every(
      (item) => item.attributes('keyword') === 'student001'
    )).toBe(true)
    await input.setValue('')
    expect(group.findAll('manual-material-review-stub').every(
      (item) => item.attributes('keyword') === ''
    )).toBe(true)
  }
  await groups[0].get('input[type="search"]').setValue('student002')
  await groups[0].get('form').trigger('submit')
  expect(wrapper.getComponent(TeacherCompetitionReview).props('keyword')).toBe('student002')
  expect(groups[0].get('manual-material-review-stub').attributes('keyword')).toBe('student002')
  expect(groups[1].get('manual-material-review-stub').attributes('keyword')).toBe('')
  wrapper.unmount()
})

it('hides empty search categories and reports an entirely empty group only after success', async () => {
  const wrapper = mount(PendingReview, {
    props: { history: true },
    global: { stubs: { ManualMaterialReview: true, TeacherCompetitionReview: true } }
  })
  for (const group of wrapper.findAll('details')) {
    group.element.open = true
    const input = group.get('input[type="search"]')
    await input.setValue('sample2602')
    await group.get('form').trigger('submit')
    const categories = group.findAll('.review-category')
    const children = [...group.findAllComponents(TeacherCompetitionReview),
      ...group.findAllComponents(ManualMaterialReview)]
    expect(children).toHaveLength(categories.length)
    const emitCount = (count) => children.forEach(child => child.vm.$emit('pending-count', count))
    const visible = () => categories.filter(category => category.element.style.display !== 'none')
    expect(group.find('.review-category-empty').exists()).toBe(false)
    emitCount(0)
    children.at(-1).vm.$emit('pending-count', 1)
    await wrapper.vm.$nextTick()
    expect(visible()).toHaveLength(1)
    expect(group.find('.review-category-empty').exists()).toBe(false)
    emitCount(null)
    await wrapper.vm.$nextTick()
    expect(group.find('.review-category-empty').exists()).toBe(false)
    emitCount(0)
    await wrapper.vm.$nextTick()
    expect(visible()).toHaveLength(0)
    expect(group.get('.review-category-empty').text()).toBe('本栏目暂无匹配的审核记录。')
    await input.setValue('')
    expect(visible()).toHaveLength(categories.length)
  }
  wrapper.unmount()
})

it('loads each pending card independently and compares the stored OCR fields inline', async () => {
  state.api.getCompetitionWorkbenchSummary.mockResolvedValue({
    pending_count: 2,
    items: [
      { id: 11, version: 3, status: 'submitted', student_id: 'S1', project_name: '第一份作品' },
      { id: 12, version: 7, status: 'submitted', student_id: 'S2', project_name: '第二份作品' }
    ]
  })
  let retry = false
  state.api.getCompetitionReviewContext.mockImplementation(async (id) => {
    if (id === 12 && !retry) throw new Error('第二份详情加载失败')
    return {
      record_id: id,
      material_version: id === 11 ? 3 : 7,
      attachments: [],
      confirmed_terms: { project_name: id === 11 ? '第一份作品' : '第二份作品' },
      ocr_raw_terms: id === 11 ? { report: { fields: { project_name: 'OCR 第一份', award_date: '2027-05-02' } } } : null,
      ocr_assessment: id === 11 ? {
        differences: [{ field: 'project_name', declared: '第一份作品', recognized: 'OCR 第一份' }]
      } : null,
      rule_basis: { competition_name: '设计竞赛', category: 'A', package_version: 1 },
      allowed_actions: ['approve', 'return']
    }
  })
  const wrapper = mount(TeacherCompetitionReview, { props: { detailsActive: false } })
  await flushPromises()
  expect(state.api.getCompetitionReviewContext).not.toHaveBeenCalled()
  await wrapper.setProps({ detailsActive: true })
  await flushPromises()
  const [first, second] = wrapper.findAll('.pending-card')
  expect(first.get('table').text()).toContain('OCR 第一份')
  expect(first.get('table').text()).toContain('2027-05-02')
  expect(first.get('table').text()).toContain('不一致')
  expect(second.get('[role="alert"]').text()).toContain('第二份详情加载失败')
  expect(wrapper.find('dialog').exists()).toBe(false)

  await first.get('textarea').setValue('第一份独立意见')
  retry = true
  await second.get('button').trigger('click')
  await flushPromises()
  expect(second.text()).toContain('暂无 OCR 结果')
  await second.get('textarea').setValue('第二份退回理由')
  await second.findAll('.material-review-actions button').find(button => button.text() === '退回补充').trigger('click')
  await flushPromises()
  expect(state.api.reviewCompetition).toHaveBeenCalledWith(
    12, 7, 'return', '第二份退回理由', expect.any(String), undefined
  )
  expect(first.get('textarea').element.value).toBe('第一份独立意见')
  wrapper.unmount()
})
