// @vitest-environment happy-dom
import { test, expect, vi } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { parse as parseVue } from '@vue/compiler-sfc'
import { parse as parseJs } from '@babel/parser'
vi.mock('@/stores/auth.js', () => ({
  useAuthStore: () => ({ token: null, user: { id: 1 }, logout: vi.fn() })
}))
import legacy from '../src/services/api.js'
import material from '../src/services/materialApi.js'
import certificate from '../src/services/certificateApi.js'
import ocr from '../src/services/ocrApi.js'
import workflow from '../src/services/workflowApi.js'
import rulePackages from '../src/services/competitionRulePackageApi.js'
import structured from '../src/services/structuredRuleApi.js'
import volunteer from '../src/services/volunteerApi.js'
import review from '../src/services/applicationReviewApi.js'

const manifest = process.env.API_ROUTE_MANIFEST
const modules = {
  legacy,
  material,
  certificate,
  ocr,
  workflow,
  rulePackages,
  structured,
  volunteer,
  review
}
const uuid = '01234567-1234-1234-1234-1234567890ab'
const data = {
  version: 1,
  status: 'approved',
  comment: '已核对',
  sub_type: 'honor',
  type: 'academic'
}
function value(name, module, method) {
  name = name.split('=')[0].trim()
  if (name === 'signal' || name === 'token') return undefined
  if (name === 'input') return { status: 'approved', idempotencyKey: 'audit' }
  if (name === 'confirmedTerms') return {}
  if (['ids', 'item_ids'].includes(name)) return [1]
  if (name === 'files') return [new File(['x'], 'proof.png')]
  if (name === 'file') return new File(['x'], 'proof.png')
  if (name === 'form') return new FormData()
  if (['data', 'settingsData', 'policy', 'snapshot'].includes(name)) return data
  if (['params', 'filters'].includes(name)) return {}
  if (name === 'id' && module === 'ocr') return uuid
  if (name === 'jobId') return uuid
  if (name === 'category') return module === 'legacy' ? 'graduate' : 'honor'
  if (name === 'project') return 'csp'
  if (name === 'path') return 'original.png'
  if (name === 'decision') return method === 'reviewCompetition' ? 'approve' : 'verified'
  if (name === 'action') return 'freeze'
  if (name === 'studentId') return method === 'updateStudentAdmin' ? 1 : 'S1'
  if (['comment', 'purpose', 'username', 'idempotencyKey', 'term'].includes(name)) return 'audit'
  if (['year', 'targetCycle'].includes(name)) return 2028
  return 1
}

test.skipIf(!manifest)(
  'every exported frontend request uses a registered backend method and route',
  async () => {
    const routes = JSON.parse(fs.readFileSync(manifest, 'utf8')).routes
    const calls = [],
      failures = [],
      methods = []
    const original = globalThis.fetch
    globalThis.fetch = vi.fn(async (url, options = {}) => {
      calls.push({
        path: new URL(String(url), 'http://localhost').pathname,
        method: options.method || 'GET'
      })
      return new Response(JSON.stringify({ id: 1 }), {
        headers: { 'Content-Type': 'application/json' }
      })
    })
    try {
      for (const [module, api] of Object.entries(modules))
        for (const [method, fn] of Object.entries(api)) {
          if (method === 'buildStructuredRuleDraft' || method === 'apiRequest') continue
          const match =
            fn.toString().match(/^(?:async\s+)?(?:\(([\s\S]*?)\)|([^=(\s]+))\s*=>/) ||
            fn.toString().match(/^(?:async\s+)?function\s+\w+\s*\(([^)]*)\)/)
          if (!match) {
            failures.push(`${module}.${method}: cannot inspect arguments`)
            continue
          }
          const params = (match[1] ?? match[2] ?? '').split(',').filter((x) => x.trim())
          const before = calls.length
          try {
            const result = await fn(...params.map((name) => value(name, module, method)))
            if (typeof result === 'string' && result.startsWith('/api/'))
              calls.push({ path: result, method: 'GET' })
          } catch (e) {
            failures.push(`${module}.${method}: ${e.message}`)
          }
          methods.push(`${module}.${method}`)
          if (calls.length === before)
            failures.push(`${module}.${method}: did not produce a request`)
        }
    } finally {
      globalThis.fetch = original
    }
    const sourceCalls = []
    function visit(node, file) {
      if (!node || typeof node !== 'object') return
      if (node.type === 'CallExpression' && node.callee?.name === 'fetch') {
        const arg = node.arguments[0]
        const url =
          arg?.type === 'StringLiteral'
            ? arg.value
            : arg?.type === 'TemplateLiteral'
              ? arg.quasis.map((x) => x.value.cooked).join('1')
              : null
        if (url?.startsWith('/api/') && file.endsWith('.vue')) {
          const options = node.arguments[1]
          const property = options?.properties?.find((p) => p.key?.name === 'method')
          const method = property?.value?.type === 'StringLiteral' ? property.value.value : 'GET'
          sourceCalls.push({ path: url.split('?')[0], method, file })
        }
      }
      for (const value of Object.values(node)) {
        if (Array.isArray(value)) value.forEach((v) => visit(v, file))
        else if (value && typeof value === 'object') visit(value, file)
      }
    }
    for (const file of fs
      .readdirSync('src', { recursive: true })
      .filter((p) => /\.(vue|js)$/.test(p))) {
      const contents = fs.readFileSync(path.join('src', file), 'utf8')
      const descriptor = file.endsWith('.vue') ? parseVue(contents).descriptor : null
      const code = descriptor
        ? [descriptor.script?.content || '', descriptor.scriptSetup?.content || ''].join(
            String.fromCharCode(10)
          )
        : contents
      visit(parseJs(code, { sourceType: 'module' }), file)
    }
    calls.push(...sourceCalls)
    for (const call of calls) {
      if (
        !routes.some(
          (route) =>
            route.methods.includes(call.method) && new RegExp(route.pattern).test(call.path)
        )
      )
        failures.push(`${call.method} ${call.path}: no backend route`)
    }
    if (process.env.API_AUDIT_OUTPUT)
      fs.writeFileSync(
        process.env.API_AUDIT_OUTPUT,
        JSON.stringify({ methods, calls, failures }, null, 2)
      )
    expect(failures).toEqual([])
    expect(methods.length).toBeGreaterThan(100)
    console.log(
      `Audited ${methods.length} frontend adapters / ${calls.length} requests against ${routes.length} backend routes`
    )
  }
)
