import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

test('role layouts push in-app page navigation so browser back returns to the previous page', () => {
  const student = read('../src/pages/student/StudentLayout.vue')
  assert.match(student, /router\.push\(\{ query: \{ page \} \}\)/)
  assert.match(student, /router\.push\(\{ query \}\)/)
  assert.match(student, /router\.push\(\{ query: \{ \.\.\.route\.query, page: 'profile' \} \}\)/)

  for (const path of [
    '../src/pages/teacher/TeacherLayout.vue',
    '../src/pages/admin/AdminLayout.vue'
  ]) {
    const source = read(path)
    assert.match(source, /router\.push\(\{ query: \{ \.\.\.route\.query, page \} \}\)/)
    assert.doesNotMatch(source, /router\.replace\(\{ query: \{ \.\.\.route\.query, page \} \}\)/)
  }
})

test('material and competition history actions push instead of replacing', () => {
  for (const path of [
    '../src/pages/student/applications/MaterialWorkflow.vue',
    '../src/pages/student/applications/StudentMaterialsHub.vue',
    '../src/pages/student/applications/CompetitionWorkflow.vue'
  ]) {
    assert.match(read(path), /router\.push\(\{ query:/)
  }
})

test('login success replaces the login history entry', () => {
  const source = read('../src/pages/common/login/Login.vue')
  assert.match(source, /await router\.replace\(routeMap\[authStore\.role\]\)/)
  assert.doesNotMatch(source, /router\.push\(routeMap\[authStore\.role\]\)/)
})
