<template>
  <section class="structured-rule card" aria-labelledby="structured-rule-title">
    <div class="section-heading">
      <div>
        <h2 id="structured-rule-title">结构化计分规则</h2>
        <p>完整词条唯一匹配后才可发布；空的可选维度将明确表示“任意”。</p>
      </div>
      <span v-if="draft" class="status-badge">草稿 #{{ draft.id }}</span>
    </div>

    <form class="rule-grid" @submit.prevent="createAndPreview">
      <label>规则名称<input v-model.trim="form.name" required /></label>
      <label>学院
        <select v-model="form.facultyId" required>
          <option disabled value="">请选择学院</option>
          <option v-for="faculty in faculties" :key="faculty.id" :value="faculty.id">
            {{ faculty.name }}
          </option>
        </select>
      </label>
      <label>材料类别<input value="学业竞赛" disabled /></label>
      <label>竞赛名称<input v-model.trim="form.competitionName" required /></label>
      <label>奖项等级<input v-model.trim="form.awardLevel" required placeholder="例如：三等奖" /></label>
      <label>竞赛级别<input v-model.trim="form.competitionLevel" placeholder="留空表示任意" /></label>
      <label>赛区<input v-model.trim="form.region" placeholder="留空表示任意" /></label>
      <label>组别<input v-model.trim="form.group" placeholder="留空表示任意" /></label>
      <label>赛道<input v-model.trim="form.track" placeholder="留空表示任意" /></label>
      <label>候选分<input v-model.number="form.score" type="number" min="0" step="0.01" required /></label>
      <label class="wide">说明<textarea v-model.trim="form.description" rows="2" /></label>
      <div class="wide actions">
        <button class="btn btn-outline" type="submit" :disabled="busy || published">
          {{ busy ? '正在检查…' : '保存草稿并预览' }}
        </button>
        <button class="btn" type="button" :disabled="!canPublish || busy" @click="publish">
          {{ publishing ? '正在发布…' : '发布规则' }}
        </button>
      </div>
    </form>

    <p v-if="errorMessage" class="feedback error" role="alert">{{ errorMessage }}</p>
    <div v-if="preview" class="preview" aria-live="polite">
      <p><strong>候选分：</strong>{{ draft.score }} 分 · 周期 {{ preview.cycle_code }}</p>
      <p v-if="preview.publishable" class="feedback success">未发现重叠，可发布。</p>
      <div v-else class="feedback error">
        <strong>存在发布冲突，不能发布。</strong>
        <span>冲突规则：{{ conflictText }}</span>
      </div>
    </div>
    <p v-if="published" class="feedback success">规则已发布，版本 #{{ published.rule_version_id }}</p>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import structuredRuleApi from '@/services/structuredRuleApi.js'

const props = defineProps({
  faculties: { type: Array, default: () => [] },
  defaultFacultyId: { type: [String, Number], default: '' }
})
const emit = defineEmits(['published'])
const form = reactive({ name: '', facultyId: '', competitionName: '', awardLevel: '',
  competitionLevel: '', region: '', group: '', track: '', score: 0, description: '' })
const draft = ref(null)
const preview = ref(null)
const published = ref(null)
const busy = ref(false)
const publishing = ref(false)
const errorMessage = ref('')

watch(() => props.defaultFacultyId, value => { if (!form.facultyId && value) form.facultyId = value }, { immediate: true })
const conflictText = computed(() => preview.value?.conflicts?.length ? preview.value.conflicts.join('、') : '未知')
const canPublish = computed(() => draft.value && preview.value?.publishable && !published.value)

function useUncoveredTerms(item) {
  const terms = item?.normalized_terms || {}
  form.facultyId = item?.faculty_id || props.defaultFacultyId || ''
  form.competitionName = terms.competition_name || ''
  form.awardLevel = terms.award_level || ''
  form.competitionLevel = terms.competition_level || ''
  form.region = terms.region || ''
  form.group = terms.group || ''
  form.track = terms.track || ''
  form.name = [form.competitionName, form.awardLevel].filter(Boolean).join(' ')
  draft.value = null; preview.value = null; published.value = null; errorMessage.value = ''
}

defineExpose({ useUncoveredTerms })

async function createAndPreview() {
  if (busy.value) return
  busy.value = true; errorMessage.value = ''; preview.value = null; published.value = null
  try {
    const payload = structuredRuleApi.buildStructuredRuleDraft(form)
    if (!payload.name) throw new TypeError('规则名称不能为空')
    draft.value = await structuredRuleApi.createStructuredRuleDraft(payload)
    preview.value = await structuredRuleApi.previewStructuredRule(draft.value.id)
  } catch (error) {
    errorMessage.value = error.message
  } finally { busy.value = false }
}

async function publish() {
  if (!canPublish.value || publishing.value) return
  publishing.value = true; errorMessage.value = ''
  try {
    published.value = await structuredRuleApi.publishStructuredRule(draft.value.id, draft.value.draft_version)
    emit('published', published.value.rule)
  } catch (error) {
    const conflicts = error.payload?.conflicts
    errorMessage.value = conflicts?.length ? `${error.message}：${conflicts.join('、')}` : error.message
  } finally { publishing.value = false }
}
</script>

<style scoped>
.structured-rule { margin-bottom: 1.25rem; padding: 1.25rem; }
.section-heading { display:flex; justify-content:space-between; gap:1rem; align-items:start; }
.section-heading h2 { margin:0 0 .35rem; font-size:1.15rem; }
.section-heading p { margin:0 0 1rem; color:#667085; }
.rule-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:.9rem; }
label { display:flex; flex-direction:column; gap:.35rem; font-size:.9rem; color:#344054; }
input, select, textarea { border:1px solid #d0d5dd; border-radius:6px; padding:.6rem; font:inherit; }
.wide { grid-column:1 / -1; }
.actions { display:flex; flex-direction:row; justify-content:flex-end; }
.feedback { margin:.9rem 0 0; padding:.7rem .85rem; border-radius:6px; }
.feedback.success { background:#ecfdf3; color:#027a48; }
.feedback.error { background:#fef3f2; color:#b42318; }
.feedback span { display:block; margin-top:.25rem; }
.preview { margin-top:.8rem; }
</style>
