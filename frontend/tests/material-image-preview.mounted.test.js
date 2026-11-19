// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
import Preview from '../src/components/common/MaterialImagePreview.vue'
import Assessment from '../src/components/common/OcrAssessment.vue'
let wrappers = []
const render = (component, props) => {
  const w = mount(component, { props, attachTo: document.body })
  wrappers.push(w)
  return w
}
beforeEach(() => {
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:proof-preview')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
})
afterEach(() => {
  wrappers.forEach((w) => w.unmount())
  wrappers = []
  document.body.style.overflow = ''
  document.body.innerHTML = ''
  vi.restoreAllMocks()
})
test('selected image is a thumbnail button, opens a large preview and closes with Escape', async () => {
  const file = new File(['image'], 'proof.jpg', { type: 'image/jpeg' })
  const w = render(Preview, { files: [file] })
  expect(w.get('img').attributes('src')).toBe('blob:proof-preview')
  expect(w.find('a[download]').exists()).toBe(false)
  await w.get('img').trigger('load')
  expect(w.text()).not.toContain('正在加载预览')
  await w.get('.thumbnail').trigger('click')
  await flushPromises()
  let dialog = document.querySelector('[role=dialog]')
  expect(dialog).not.toBeNull()
  expect(dialog.querySelector('img').src).toBe('blob:proof-preview')
  expect(dialog.querySelector('button')).toBe(document.activeElement)
  expect(document.body.style.overflow).toBe('hidden')
  dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
  await flushPromises()
  expect(document.querySelector('[role=dialog]')).toBeNull()
  expect(document.body.style.overflow).toBe('')
  expect(document.activeElement).toBe(w.get('.thumbnail').element)
})
test('saved images use protected inline URLs, and the close button never downloads them', async () => {
  const w = render(Preview, {
    attachments: [
      { id: 1, filename: 'proof.png', url: '/api/materials/competition/records/1/attachments/1' }
    ]
  })
  expect(w.get('img').attributes('src')).toBe(
    '/api/materials/competition/records/1/attachments/1?inline=1'
  )
  await w.get('button').trigger('click')
  await flushPromises()
  expect(document.querySelector('[role=dialog] img').getAttribute('src')).toContain('?inline=1')
  document.querySelector('.close-preview').click()
  await flushPromises()
  expect(document.querySelector('[role=dialog]')).toBeNull()
  expect(w.find('a').exists()).toBe(false)
})
test('changing files releases the old image and unmount releases the remaining preview', async () => {
  const w = render(Preview, { files: [new File(['a'], 'first.png')] })
  await w.get('button').trigger('click')
  await flushPromises()
  await w.setProps({ files: [new File(['b'], 'next.jpg')] })
  expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1)
  expect(document.querySelector('[role=dialog]')).toBeNull()
  expect(w.text()).toContain('next.jpg')
  w.unmount()
  wrappers = []
  expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2)
})
test('nonimages are identified and failed images have an actionable preview state', async () => {
  const w = render(Preview, {
    files: [new File(['pdf'], 'proof.pdf'), new File(['bad'], 'broken.png')]
  })
  expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
  expect(w.text()).toContain('proof.pdf（非图片文件）')
  await w.get('img').trigger('error')
  expect(w.text()).toContain('点击重试预览')
  await w.get('button').trigger('click')
  await flushPromises()
  document.querySelector('[role=dialog] img').dispatchEvent(new Event('error'))
  await flushPromises()
  expect(document.querySelector('[role=alert]').textContent).toContain('图片加载失败')
})
test('score-only preview contains exactly the requested conditional sentence', () => {
  const w = render(Assessment, {
    advice: {
      declared_estimate: '1.6667',
      notice: '按手填信息计算单项候选分；最终计入分受审核、去重与上限影响。'
    }
  })
  expect(w.get('p').text().replace(/\s+/g, '')).toBe(
    '如材料属实且与申报信息相符，审核通过后本项预计可得1.6667分。'
  )
  expect(w.get('strong').text()).toBe('1.6667')
  expect(w.findAll('p')).toHaveLength(1)
  expect(w.find('small').exists()).toBe(false)
  expect(w.text()).not.toContain('尚无OCR任务')
})
test('completed OCR retains the differences and verification guidance', () => {
  const w = render(Assessment, {
    advice: {
      declared_estimate: '1.6667',
      job: { status: 'completed' },
      differences: [{ field: 'award', declared: 'first_or_above', recognized: 'second' }],
      missing_fields: ['level']
    }
  })
  expect(w.text()).toContain('奖项不一致')
  expect(w.text()).toContain('竞赛级别')
  expect(w.text()).toContain('教师人工核对')
})
