import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { buildStudentBaseUpdate, scoreAuthorityMeta } from '../src/services/adminScorePresentation.js'

test('admin student update payload excludes every derived score and ranking field',()=>{
  const payload=buildStudentBaseUpdate({id:1,student_id:'S1',student_name:'张三',gender:'男',academic_score:90,
    academic_specialty_total:99,comprehensive_performance_total:99,total_score:999,
    comprehensive_score:999,major_ranking:1,total_students:1,facultyName:'信息学院'})
  assert.deepEqual(payload,{student_name:'张三',gender:'男',academic_score:90})
  for(const field of ['academic_specialty_total','comprehensive_performance_total','total_score','comprehensive_score','major_ranking','total_students']) assert(!(field in payload))
})

test('score page shows derived fields read-only with snapshot authority metadata',()=>{
  const source=readFileSync(new URL('../src/pages/admin/scores/ScoreManagement.vue',import.meta.url),'utf8')
  assert.match(source,/buildStudentBaseUpdate\(this\.formData\)/)
  assert.match(source,/snapshot_version/);assert.match(source,/snapshot_status/);assert.match(source,/snapshot_updated_at/)
  assert.deepEqual(scoreAuthorityMeta({snapshot_version:3,snapshot_status:'current',snapshot_updated_at:'now'}),{version:3,status:'current',updatedAt:'now'})
})
