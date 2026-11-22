import { test, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import workflowApi from '../src/services/workflowApi.js'

const originalFetch=globalThis.fetch
afterEach(()=>{globalThis.fetch=originalFetch})
test('each ranking lifecycle action sends exactly one versioned request',async()=>{
  const calls=[];globalThis.fetch=async(url,options)=>{calls.push({url,...options});return new Response(JSON.stringify({batch_id:7,version:2,status:'frozen',allowed_actions:[],entries:[]}))}
  for(const action of ['freeze','request_correction','publish','withdraw','create_successor'])
    await workflowApi.rankingCommand(7,action,2,`${action}-key`,action.includes('correction')?{reason:'修正'}:{})
  assert.equal(calls.length,5)
  for(const [index,action] of ['freeze','request_correction','publish','withdraw','create_successor'].entries()){
    assert.equal(calls[index].url,`/api/workflow/rankings/7/commands/${action}`)
    assert.equal(JSON.parse(calls[index].body).version,2)
    assert.equal(JSON.parse(calls[index].body).idempotency_key,`${action}-key`)
  }
})

test('admin ranking page renders command buttons only from allowed_actions',()=>{
  const source=readFileSync(new URL('../src/pages/admin/rankings/RankingPublication.vue',import.meta.url),'utf8')
  assert.match(source,/ranking\.allowed_actions\.filter/)
  assert.match(source,/workflowApi\.rankingCommand/)
  assert.equal((source.match(/workflowApi\.rankingCommand/g)||[]).length,1)
  assert.match(source,/blockers/)
})
