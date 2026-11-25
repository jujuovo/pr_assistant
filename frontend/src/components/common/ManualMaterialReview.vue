<template>
  <section class="manual-review" :class="{ 'manual-review-embedded': fixedCategory }"
    ><header v-if="!fixedCategory">
      <h2>{{ history ? '其他材料核验记录' : '其他材料人工核验' }}</h2>
    </header>
    <label v-if="!fixedCategory"
      >材料类别<select v-model="category" @change="load"
        ><option v-for="[key, name] in kinds" :key="key" :value="key">{{ name }}</option></select
      ></label
    >
    <p v-if="loading" role="status">正在加载材料…</p
    ><p v-if="error" role="alert">{{ error }} <button @click="load">重新加载</button></p
    ><p v-if="!loading && !error && !rows.length" class="review-category-empty" role="status">当前类别暂无{{ history ? '核验记录' : '待核验材料' }}。</p>
    <article v-for="row in rows" :key="row.id" class="material-review-card"
      ><ReviewStatusBadge v-if="history && compareEvidence" :status="row.status" />
      <h3>学生 {{ row.student_id }} · 材料 #{{ row.id }}</h3
      ><VolunteerOcrAssessment
        :assessment="row.volunteer_ocr"
        :appeal="row.appeal"
        :priority="row.priority_review"
        :reports="row.ocr_raw_terms?.reports || []"
      />
      <ReviewEvidenceLayout v-if="compareEvidence" :attachments="row.attachments">
        <MaterialReviewComparison
          v-if="row.category !== 'volunteer' || !row.volunteer_ocr"
          :declared="row.data"
          :recognized="row.ocr_raw_terms?.report?.fields || row.ocr_raw_terms?.fields || {}"
          :labels="row.category === 'volunteer' ? { award_date: '服务记录日期' } : row.category === 'arts_sports' ? { award_date: '获得时间' } : {}"
        />
      </ReviewEvidenceLayout>
      <template v-else>
      <h4>学生申报值</h4
      ><MaterialFacts
        :data="row.data"
        :labels="
          row.category === 'volunteer'
            ? { award_date: '服务记录日期' }
            : row.category === 'arts_sports'
              ? { award_date: '获得时间' }
              : {}
        "
      />
      </template>
      <p v-if="row.analysis?.submitted_hours"
        >本次有效工时：{{
          row.analysis.submitted_hours.effective_hours
        }}
        小时；审核通过后计入累计。</p
      >
      <details v-if="!compareEvidence && row.category !== 'volunteer'"
        ><summary>核对原始识别</summary><MaterialFacts :data="row.ocr_raw_terms?.fields || {}"
      /></details>
      <MaterialImagePreview v-if="!compareEvidence" :attachments="row.attachments || []" />
      <PolicyMaterialFields v-if="!history && policy(row) && row.category !== 'student_work' && row.allowed_actions?.includes('review')" v-model="facts[row.id]" :category="row.category" review />
      <template v-if="!history && policy(row) && row.category === 'student_work' && row.allowed_actions?.includes('review')">
        <fieldset v-for="(a,i) in facts[row.id].assessments" :key="i"><legend>核定任职 {{a.appointment_index+1}}</legend>
        <label v-for="(label,key) in assessmentLabels" :key="key">{{label}}
        <select v-if="options[key]" v-model="a[key]"><option v-for="[v,l] in options[key]" :key="v" :value="v">{{l}}</option></select>
        <input v-else v-model="a[key]" :type="key==='proof_date'?'date':['academic_year','assessment_score'].includes(key)?'number':'text'" /></label>
        <button type="button" @click="facts[row.id].assessments.push({appointment_index:a.appointment_index})">为此任职增加学年</button></fieldset></template>
      <ReviewCommentForm v-if="!history && row.allowed_actions?.includes('review')"
        :comment-id="'comment-' + row.id" v-model="comments[row.id]">
        <button v-for="[decision, label] in decisions" :key="decision"
          class="btn btn-outline" type="button" :disabled="busy"
          @click="review(row, decision)">{{ label }}</button>
      </ReviewCommentForm>
      <button v-if="history" class="btn btn-outline" @click="events(row)">查看核验意见</button
      ><ol v-if="audit[row.id]"
        ><li v-for="event in audit[row.id]" :key="event.id"
          >{{ event.details.comment || '材料状态已更新' }} · {{ event.created_at }}</li
        ></ol
      > </article
    ><p v-if="notice" role="status">{{ notice }}</p></section
  >
</template>
<script setup>
import { ref, watch } from 'vue'
import materialApi from '@/services/materialApi.js'
import PolicyMaterialFields from './PolicyMaterialFields.vue'
import ReviewStatusBadge from '@/components/teacher/ReviewStatusBadge.vue'
import ReviewCommentForm from '@/components/teacher/ReviewCommentForm.vue'
import ReviewEvidenceLayout from '@/components/teacher/ReviewEvidenceLayout.vue'
import MaterialReviewComparison from '@/components/teacher/MaterialReviewComparison.vue'
import MaterialFacts from './MaterialFacts.vue'
import MaterialImagePreview from './MaterialImagePreview.vue'
import VolunteerOcrAssessment from './VolunteerOcrAssessment.vue'
import { manualReviewCategories } from '@/services/teacherReviewCategories.js'
const props = defineProps({ history: Boolean, compareEvidence: Boolean, fixedCategory: String, keyword: String })
const emit = defineEmits(['pending-count'])
const kinds = [['all', '全部类别'], ...manualReviewCategories]
const decisions = [
  ['verified', '核验通过'],
  ['needs_correction', '退回补充'],
  ['rejected', '核验不通过']
]
const category = ref(props.fixedCategory || 'all'),
  rows = ref([]),
  error = ref(''),
  loading = ref(false),
  busy = ref(false),
  comments = ref({}),
  notice = ref(''),
  audit = ref({})
const facts=ref({})
const assessmentLabels={academic_year:'任职学年起始年份',mapped_position:'条例岗位全称',mapping_basis:'岗位对应依据',scope:'组织范围',tenure:'任期档位',tenure_basis:'任期依据',assessment_score:'考核分',assessor_role:'考核人身份',assessment_source:'考核来源',proof_date:'证明落款日期'}
const options={scope:[['college','院级'],['university','校级']],tenure:[['below_semester','不足一学期'],['semester','满一学期不足一学年'],['full_year','满一学年']],assessor_role:[['辅导员','辅导员'],['指导老师','指导老师']]}
function policy(row){return ['research_paper','invention_patent','innovation_training'].includes(row.category) || row.normalization_version==='info-student-work-2025-02'}
let loadVersion = 0
async function load() {
  const version = ++loadVersion
  const keyword = props.history ? props.keyword : undefined
  rows.value=[]
  loading.value = true
  error.value = ''
  const selected = category.value
  const categories =
    selected === 'all'
      ? kinds.filter(([key]) => key !== 'all').map(([key]) => key)
      : [selected]
  try {
    const results = await Promise.allSettled(
      categories.map(async (key) => {
        const records = []
        let afterId
        do {
          const page = await materialApi.listRecords(key, {
            reviewed: props.history ? '1' : '0',
            keyword,
            after_id: afterId
          })
          records.push(...(page.records || []))
          afterId = page.next_after_id
        } while (keyword && afterId && version === loadVersion)
        return { records }
      })
    )
    if (version !== loadVersion) return
    const merged = []
    const failures = []
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        merged.push(...(result.value.records || []))
      } else {
        const name = kinds.find(([key]) => key === categories[index])?.[1]
        failures.push(name || categories[index])
      }
    })
    for (const row of merged.filter(policy))
      facts.value[row.id] = row.category === 'student_work'
        ? { assessments: row.data.appointments.map((_, appointment_index) => ({ appointment_index })) }
        : JSON.parse(JSON.stringify(row.data))
    rows.value = merged
      .sort((a, b) => Number(!!b.priority_review) - Number(!!a.priority_review))
      .filter(
        (row) =>
          (policy(row) || row.manual_only || row.category === 'volunteer') &&
          (props.history
            ? [
                'verified',
                'rejected',
                'needs_correction',
                'scored',
                'verified_not_eligible'
              ].includes(row.status)
            : ['submitted','under_review'].includes(row.status))
      )
    if (failures.length) error.value = '以下类别未能加载，请重试：' + failures.join('、')
  } catch (e) {
    if (version === loadVersion) error.value = e.message
  } finally {
    if (version === loadVersion) {
      if (props.fixedCategory) emit('pending-count', error.value ? null : rows.value.length)
      loading.value = false
    }
  }
}
async function review(row, decision) {
  if ((policy(row) || decision !== 'verified') && !comments.value[row.id]?.trim()) {
    error.value = '请先填写具体的核验意见。'
    document.getElementById('comment-' + row.id)?.focus()
    return
  }
  busy.value = true
  error.value = ''
  try {
    await materialApi.review(
      row.category,
      row.id,
      row.version,
      decision,
      comments.value[row.id] || '',
      ...(policy(row) ? [{idempotency_key: crypto.randomUUID(), ...(decision==='verified'?{verified_facts:facts.value[row.id]}:{})}] : [])
    )
    notice.value = '核验结果已保存。'
    await load()
  } catch (e) {
    error.value = e.status === 409 ? '材料版本已变化，请刷新后核对最新内容。' : e.message
  } finally {
    busy.value = false
  }
}
async function events(row) {
  try {
    audit.value[row.id] = (await materialApi.getEvents(row.category, row.id)).events.filter(
      (e) => e.action === 'reviewed'
    )
  } catch (e) {
    error.value = e.message
  }
}
watch(() => props.keyword, load, { immediate: true })
</script>
<style scoped>
@import '@/assets/styles/pages/teacher/reviews/MaterialReviewCard.css';

.manual-review {
  display: grid;
  gap: 14px;
  padding: 22px;
  margin: 20px 0;
  border: 1px solid #dce5ef;
  border-radius: 12px;
  background: #fff;
}
.manual-review-embedded {
  padding: 0;
  margin: 0;
  border: 0;
  background: transparent;
}
.manual-review h2,
.manual-review p {
  margin: 0;
}
.manual-review label {
  display: grid;
  gap: 6px;
}
.manual-review select,
.manual-review textarea {
  padding: 10px;
  border: 1px solid #b9c7d8;
  border-radius: 7px;
}
.original-image {
  display: block;
  max-width: 100%;
  max-height: 360px;
  object-fit: contain;
  margin: 12px 0;
}
</style>
