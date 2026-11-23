// @vitest-environment happy-dom
import { mount } from '@vue/test-utils'
import { expect, test } from 'vitest'
import Assessment from '../src/components/common/OcrAssessment.vue'
const advice = {
  declared_estimate: '0.6667', ocr_suggested_score: '0.6667',
  job: { status: 'completed' }, missing_fields: ['level', 'recognition_quality'],
  notice: '内部识别说明', review_mode: 'manual_confirmation', differences: []
}
test('student sees labelled large score cards and submission guidance without technical noise', () => {
  const w = mount(Assessment, { props: { advice, conciseEstimate: true, readyToSubmit: true } })
  expect(w.findAll('.score-card dt').map(el => el.text())).toEqual(['申请分数', '系统建议分数'])
  expect(w.findAll('.score-card strong').map(el => el.text())).toEqual(['0.6667', '0.6667'])
  expect(w.text()).toContain('确认无误后点击“正式提交审核”')
  for (const text of ['OCR 尚不足', '内部识别说明', '条件性', '规则辅助', '识别质量与证书字段']) expect(w.text()).not.toContain(text)
  w.unmount()
})
test('missing suggestion is not replaced by zero or the declared score; a real zero remains numeric', () => {
  const missing = mount(Assessment, { props: { advice: { ...advice, ocr_suggested_score: null }, conciseEstimate: true } })
  expect(missing.findAll('.score-card')[1].text()).toContain('需人工核验')
  expect(missing.findAll('.score-card')[1].find('strong').exists()).toBe(false)
  missing.unmount()
  const zero = mount(Assessment, { props: { advice: { ...advice, declared_estimate: 0, ocr_suggested_score: 0 }, conciseEstimate: true } })
  expect(zero.findAll('.score-card strong').map(el => el.text())).toEqual(['0', '0'])
  zero.unmount()
})
test.each(['queued', 'running', 'failed', 'stale'])('student handles %s without showing an old suggestion', (status) => {
  const w = mount(Assessment, { props: { advice: { ...advice, job: { status } }, conciseEstimate: true } })
  expect(w.findAll('.score-card')[1].find('strong').exists()).toBe(false)
  expect(w.text()).not.toContain('确认无误后点击')
  expect(w.find('.difference-list').exists()).toBe(false)
  w.unmount()
})
test('differences show both values with a red warning class, while teacher diagnostics remain available', () => {
  const result = { ...advice, differences: [{ field: 'award', declared: 'third', recognized: 'second' }] }
  const student = mount(Assessment, { props: { advice: result, conciseEstimate: true } })
  expect(student.get('.difference-list').text()).toContain('奖项不一致')
  expect(student.get('.difference-list').text()).toContain('三等奖')
  expect(student.get('.difference-list').text()).toContain('二等奖')
  student.unmount()
  const teacher = mount(Assessment, { props: { advice: result } })
  expect(teacher.text()).toContain('OCR 尚不足以核验')
  expect(teacher.text()).toContain('竞赛级别')
  teacher.unmount()
})
