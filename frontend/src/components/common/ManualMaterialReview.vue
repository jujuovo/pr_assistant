<template>
  <section class="manual-review"
    ><header
      ><h2>{{ history ? '其他材料核验记录' : '其他材料人工核验' }}</h2
      ><p>{{
        category === 'volunteer'
          ? '请核对本次工时证明、服务记录日期、服务对象认可，以及大型赛会和支教工时分类。通过后计入该学生本周期累计工时，并按学院办法计分。'
          : '原件、OCR识别和学生申报值分别展示；本通道核验不生成加分。'
      }}</p></header
    >
    <label
      >材料类别<select v-model="category" @change="load"
        ><option v-for="[key, name] in kinds" :key="key" :value="key">{{ name }}</option></select
      ></label
    >
    <p v-if="loading" role="status">正在加载材料…</p
    ><p v-if="error" role="alert">{{ error }} <button @click="load">重新加载</button></p
    ><p v-if="!loading && !rows.length">当前类别暂无{{ history ? '核验记录' : '待核验材料' }}。</p>
    <article v-for="row in rows" :key="row.id"
      ><h3>学生 {{ row.student_id }} · 材料 #{{ row.id }}</h3
      ><VolunteerOcrAssessment
        :assessment="row.volunteer_ocr"
        :appeal="row.appeal"
        :priority="row.priority_review"
        :reports="row.ocr_raw_terms?.reports || []"
      />
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
      <p v-if="row.analysis?.submitted_hours"
        >本次有效工时：{{
          row.analysis.submitted_hours.effective_hours
        }}
        小时；审核通过后计入累计。</p
      >
      <details v-if="row.category !== 'volunteer'"
        ><summary>核对原始识别</summary><MaterialFacts :data="row.ocr_raw_terms?.fields || {}"
      /></details>
      <MaterialImagePreview :attachments="row.attachments || []" />
      <template v-if="!history && row.status === 'submitted'"
        ><label :for="'comment-' + row.id"
          >核验意见（通过时选填；退回或不通过时必填）<textarea
            :id="'comment-' + row.id"
            v-model="comments[row.id]"
            maxlength="2000"
          /></label
        ><div class="actions"
          ><button
            v-for="[decision, label] in decisions"
            :key="decision"
            class="btn btn-outline"
            :disabled="busy"
            @click="review(row, decision)"
            >{{ label }}</button
          ></div
        ></template
      >
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
import { ref, onMounted } from 'vue'
import materialApi from '@/services/materialApi.js'
import MaterialFacts from './MaterialFacts.vue'
import MaterialImagePreview from './MaterialImagePreview.vue'
import VolunteerOcrAssessment from './VolunteerOcrAssessment.vue'
const props = defineProps({ history: { type: Boolean, default: false } })
const kinds = [
  ['all', '全部类别'],
  ['volunteer', '志愿服务累计工时'],
  ['competition_evidence', '目录外竞赛'],
  ['certification', '认证成绩'],
  ['social_practice', '社会实践'],
  ['research', '成果检索报告'],
  ['student_work', '学生工作'],
  ['arts_sports', '文体活动']
]
const decisions = [
  ['verified', '核验通过'],
  ['needs_correction', '退回补充'],
  ['rejected', '核验不通过']
]
const category = ref('all'),
  rows = ref([]),
  error = ref(''),
  loading = ref(false),
  busy = ref(false),
  comments = ref({}),
  notice = ref(''),
  audit = ref({})
async function load() {
  loading.value = true
  error.value = ''
  const selected = category.value
  const categories =
    selected === 'all'
      ? kinds.filter(([key]) => key !== 'all').map(([key]) => key)
      : [selected]
  try {
    const results = await Promise.allSettled(
      categories.map((key) =>
        materialApi.listRecords(key, { reviewed: props.history ? '1' : '0' })
      )
    )
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
    rows.value = merged
      .sort((a, b) => Number(!!b.priority_review) - Number(!!a.priority_review))
      .filter(
        (row) =>
          (row.manual_only || row.category === 'volunteer') &&
          (props.history
            ? [
                'verified',
                'rejected',
                'needs_correction',
                'scored',
                'verified_not_eligible'
              ].includes(row.status)
            : row.status === 'submitted')
      )
    if (failures.length) error.value = '以下类别未能加载，请重试：' + failures.join('、')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function review(row, decision) {
  if (decision !== 'verified' && !comments.value[row.id]?.trim()) {
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
      comments.value[row.id] || ''
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
onMounted(load)
</script>
<style scoped>
.manual-review {
  display: grid;
  gap: 14px;
  padding: 22px;
  margin: 20px 0;
  border: 1px solid #dce5ef;
  border-radius: 12px;
  background: #fff;
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
.manual-review article {
  padding: 18px;
  border: 1px solid #dce5ef;
  border-radius: 9px;
}
.manual-review textarea {
  min-height: 70px;
}
.original-image {
  display: block;
  max-width: 100%;
  max-height: 360px;
  object-fit: contain;
  margin: 12px 0;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}
</style>
