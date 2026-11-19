import { test, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import api from '../src/services/competitionRulePackageApi.js'
import { readFileSync } from 'node:fs'

const originalFetch=globalThis.fetch
afterEach(()=>{globalThis.fetch=originalFetch})
function capture(){const calls=[];globalThis.fetch=async(url,options)=>{calls.push({url,...options});return new Response(JSON.stringify({items:[]}))};return calls}

test('2028 to 2029 package journey uses one versioned command per write',async()=>{
  const calls=capture()
  await api.copy(8,2029,'copy-key');await api.edit(9,1,{package_id:'competition-2029'})
  await api.diff(9);await api.validate(9);await api.publish(9,2,'publish-key')
  assert.deepEqual(calls.map(c=>[c.method,c.url]),[
    ['POST','/api/competition-rule-packages/copy'],['PUT','/api/competition-rule-packages/9/draft'],
    ['GET','/api/competition-rule-packages/9/diff'],['POST','/api/competition-rule-packages/9/validate'],
    ['POST','/api/competition-rule-packages/9/publish']])
  assert.deepEqual(JSON.parse(calls[0].body),{source_package_id:8,target_cycle:2029,idempotency_key:'copy-key'})
  assert.deepEqual(JSON.parse(calls[4].body),{draft_revision:2,idempotency_key:'publish-key'})
})

test('package component renders published rows read-only from allowed_actions',()=>{
  const source=readFileSync(new URL('../src/pages/admin/rules/CompetitionRulePackages.vue',import.meta.url),'utf8')
  for(const action of ['copy','edit','diff','validate','publish']) assert.match(source,new RegExp(`allowed_actions\\.includes\\('${action}'\\)`))
  assert.doesNotMatch(source,/row\.status\s*===\s*['"]draft/)
  assert.match(source,/正式包不可编辑/)
})
