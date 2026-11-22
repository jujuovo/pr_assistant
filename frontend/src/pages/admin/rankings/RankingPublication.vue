<template>
  <RankingBatch ref="workbench" title="排名发布" :disabled="busy" show-basis>
    <template #before>
      <form class="card generate-card" @submit.prevent="generate">
        <h2>生成试算批次</h2>
        <p v-if="loadError" role="alert">{{ loadError }}
          <button type="button" class="btn btn-outline" @click="loadChoices">重试</button>
        </p>
        <div class="generate-fields">
          <label>推免周期
            <select v-model.number="form.year" class="form-control" required>
              <option value="">请选择周期</option>
              <option v-for="cycle in cycles" :key="cycle.cycle_code" :value="cycle.cycle_code">{{ cycle.display_name }}</option>
            </select>
          </label>
          <label>专业
            <select v-model.number="form.major_id" class="form-control" required>
              <option value="">请选择专业</option>
              <option v-for="major in majors" :key="major.id" :value="major.id">{{ major.name }}</option>
            </select>
          </label>
          <label>成绩截止时间（北京时间）
            <input v-model="form.cutoff_at" class="form-control" type="datetime-local" required />
          </label>
        </div>
        <button class="btn btn-primary" :disabled="busy || !cycles.length || !majors.length">生成试算</button>
      </form>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="notice" role="status">{{ notice }}</p>
    </template>
    <template #actions="{ ranking, label }">
      <div class="command-actions">
        <button v-for="action in ranking.allowed_actions.filter(action => labels[action])" :key="action"
          class="btn btn-outline" type="button" :disabled="busy" @click="open(ranking, action, label)">
          {{ labels[action] }}
        </button>
        <button v-if="ranking.allowed_actions.includes('export')" class="btn btn-outline"
          type="button" @click="exporter.open(ranking)">导出名单</button>
      </div>
      <ul v-if="blockedBatchId === ranking.batch_id && blockers.length" role="alert">
        <li v-for="(item, index) in blockers" :key="index">
          {{ [item.student_id, blockerLabel(item.reason)].filter(Boolean).join(' · ') }}
        </li>
      </ul>
    </template>
  </RankingBatch>
  <RankingExport ref="exporter" />
  <dialog ref="dialog" class="ranking-dialog">
    <form v-if="pending" @submit.prevent="command">
      <h2>{{ labels[pending.action] }}排名批次</h2>
      <p>{{ pending.label }}</p>
      <label v-if="requiresReason">原因
        <textarea v-model.trim="reason" class="form-control" required maxlength="500" />
      </label>
      <p v-if="commandError" role="alert">{{ commandError }}</p>
      <button type="button" class="btn btn-outline" :disabled="busy" @click="dialog.close()">取消</button>
      <button class="btn btn-primary" :disabled="busy || (requiresReason && !reason)">确认{{ labels[pending.action] }}</button>
    </form>
  </dialog>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import RankingBatch from '@/pages/common/statistics/RankingBatch.vue'
import RankingExport from '@/components/common/RankingExport.vue'
import api from '@/services/api.js'
import workflowApi from '@/services/workflowApi.js'
import { workflowErrorMessage } from '@/services/workflowPresentation.js'
import { useAuthStore } from '@/stores/auth.js'

const auth = useAuthStore()
const workbench = ref(null)
const exporter = ref(null)
const dialog = ref(null)
const pending = ref(null)
const cycles = ref([])
const majors = ref([])
const busy = ref(false)
const reason = ref('')
const error = ref('')
const loadError = ref('')
const commandError = ref('')
const notice = ref('')
const blockers = ref([])
const blockedBatchId = ref(null)
const form = reactive({ year: '', major_id: '', cutoff_at: '' })
const labels = { freeze: '冻结', request_correction: '解冻纠错', publish: '发布', withdraw: '撤回', create_successor: '创建后继版本' }
const requiresReason = computed(() => ['request_correction', 'withdraw'].includes(pending.value?.action))

function blockerLabel(code) {
  return {
    missing_score_snapshot: '缺少成绩快照', score_snapshot_not_found: '成绩快照不存在',
    score_snapshot_changed: '成绩已更新，请重新生成试算',
    rule_version_not_bound: '批次未绑定对应的计分规则版本',
    unresolved_legacy_differences: '有尚未完成的对账事项',
    student_not_eligible: '学生不符合排名条件'
  }[code] || code
}

async function loadChoices() {
  loadError.value = ''
  try {
    const [cycleData, majorData] = await Promise.all([
      api.getRecommendationCycles(),
      api.getMajorsAdmin('', auth.user?.faculty_id || auth.user?.faculty?.id)
    ])
    const uniqueCycles = new Map()
    for (const cycle of cycleData.items) {
      if (!uniqueCycles.has(cycle.cycle_code)) uniqueCycles.set(cycle.cycle_code, cycle)
    }
    cycles.value = [...uniqueCycles.values()]
    majors.value = majorData.majors || []
    form.year = cycleData.items.find(cycle => cycle.status === 'active')?.cycle_code ?? ''
  } catch (cause) {
    loadError.value = workflowErrorMessage(cause)
  }
}

async function generate() {
  if (busy.value) return
  busy.value = true
  error.value = notice.value = ''
  try {
    const cutoff = new Date(form.cutoff_at + '+08:00').toISOString().slice(0, -1)
    const result = await workflowApi.generateRanking({
      year: form.year, major_id: form.major_id, cutoff_at: cutoff, precision: 4,
      idempotency_key: crypto.randomUUID()
    })
    await workbench.value.refresh(result.batch_id)
    notice.value = '已生成试算批次'
  } catch (cause) {
    error.value = workflowErrorMessage(cause)
  } finally {
    busy.value = false
  }
}

function open(ranking, action, label) {
  pending.value = { ranking, action, label }
  reason.value = commandError.value = ''
  dialog.value.showModal()
}

async function command() {
  if (busy.value) return
  const { ranking, action } = pending.value
  busy.value = true
  commandError.value = error.value = notice.value = ''
  blockers.value = []
  try {
    const result = await workflowApi.rankingCommand(ranking.batch_id, action, ranking.version,
      crypto.randomUUID(), requiresReason.value ? { reason: reason.value } : {})
    dialog.value.close()
    await workbench.value.refresh(result.batch_id)
    notice.value = `已完成「${labels[action]}」`
  } catch (cause) {
    blockers.value = cause.payload?.blockers || []
    blockedBatchId.value = ranking.batch_id
    if (blockers.value.length) {
      dialog.value.close()
      error.value = workflowErrorMessage(cause)
    } else {
      commandError.value = workflowErrorMessage(cause)
    }
  } finally {
    busy.value = false
  }
}

onMounted(loadChoices)
</script>

<style scoped>
.generate-card { margin-bottom: 1rem; padding: 1.25rem; }
.generate-fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr)); gap: 1rem; margin: 1rem 0; }
.generate-fields label { display: grid; gap: .5rem; }
.command-actions { display: flex; flex-wrap: wrap; gap: .75rem; margin: 1rem 0; }
.ranking-dialog { position: fixed; inset: 0; margin: auto; padding: 1.5rem; width: min(32rem, calc(100% - 2rem)); border: 1px solid #dce5ef; border-radius: .85rem; }
.ranking-dialog::backdrop { background: rgb(10 28 48 / 45%); }
</style>
