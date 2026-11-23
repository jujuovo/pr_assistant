import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

// 图标改为按需注册后（原先 library.add(fas) 会把 1600+ 个图标全打进包，实测
// 约 950 KB），新增图标若忘记在 main.js 注册，界面会静默不显示图标而不报错。
// 这个测试把"源码用到的图标"与"main.js 注册的图标"对齐，漏加会直接失败。

const srcRoot = fileURLToPath(new URL('../src', import.meta.url))
const mainPath = join(srcRoot, 'main.js')

/** 把 FontAwesome 的 camelCase 标识符还原成 kebab-case 名称。 */
function camelToKebab(identifier) {
  return identifier
    .replace(/^fa/, '')
    .replace(/([A-Z])/g, (match, letter, offset) => (offset > 0 ? '-' : '') + letter)
    .toLowerCase()
}

function walk(dir) {
  const files = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) files.push(...walk(full))
    else if (/\.(vue|js)$/.test(entry)) files.push(full)
  }
  return files
}

function registeredIcons() {
  const source = readFileSync(mainPath, 'utf8')
  const names = new Set()
  for (const match of source.matchAll(/\bfa[A-Z][A-Za-z0-9]*\b/g)) {
    names.add(camelToKebab(match[0]))
  }
  return names
}

function usedIcons() {
  const names = new Set()
  for (const file of walk(srcRoot)) {
    if (file === mainPath) continue
    const text = readFileSync(file, 'utf8')
    for (const match of text.matchAll(/\[\s*'fas'\s*,\s*'([a-z0-9-]+)'\s*\]/g)) names.add(match[1])
    for (const match of text.matchAll(/\bfa[srb]\s+fa-([a-z0-9-]+)/g)) names.add(match[1])
    for (const match of text.matchAll(/icon:\s*'([a-z0-9-]+)'/g)) names.add(match[1])
  }
  return names
}

test('每个源码中引用的 FontAwesome 图标都已在 main.js 注册', () => {
  const registered = registeredIcons()
  const missing = [...usedIcons()].filter((name) => !registered.has(name)).sort()
  assert.deepEqual(
    missing,
    [],
    `以下图标被引用但没有注册，界面会不显示：${missing.join('、')}。请在 src/main.js 的 import 与 library.add 中补上。`
  )
})

test('main.js 不再整包注册 solid 图标', () => {
  const source = readFileSync(mainPath, 'utf8')
  assert.equal(source.includes('library.add(fas)'), false, '不得回退到整包注册')
  assert.equal(/import\s*\{\s*fas\s*\}/.test(source), false, '不得回退到整包导入')
})
