<template>
  <section class="manual-review"
    ><header
      ><h2>{{ history ? '其他材料核验记录' : '其他材料人工核验' }}</h2
      ><p>原件、OCR识别和学生申报值分别展示；本通道核验不生成加分。</p></header
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
      ><h4>学生申报值</h4><MaterialFacts :data="row.data" />
      <details
        ><summary>核对原始识别</summary><MaterialFacts :data="row.ocr_raw_terms?.fields || {}"
      /></details>
      <div v-for="file in row.attachments" :key="file.id"
        ><a :href="file.url" target="_blank" rel="noopener">查看原件：{{ file.filename }}</a
        ><img
          v-if="/\.(png|jpe?g|webp)$/i.test(file.filename)"
          :src="file.url + '?inline=1'"
          :alt="file.filename + '原件'"
          class="original-image"
      /></div>
      <template v-if="!history && row.status === 'submitted'"
        ><label :for="'comment-' + row.id"
          >核验意见<textarea
            :id="'comment-' + row.id"
            v-model="comments[row.id]"
            maxlength="2000"
            required
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
const props = defineProps({ history: { type: Boolean, default: false } })
const kinds = [
  ['competition_evidence', '目录外竞赛'],
  ['certification', '认证成绩'],
  ['social_practice', '社会实践'],
  ['research', '成果检索报告'],
  ['student_work', '学生工作']
]
const decisions = [
  ['verified', '核验通过'],
  ['needs_correction', '退回补充'],
  ['rejected', '核验不通过']
]
const category = ref('social_practice'),
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
  try {
    const result = await materialApi.listRecords(category.value, {
      reviewed: props.history ? '1' : '0'
    })
    rows.value = result.records.filter(
      (row) =>
        row.manual_only &&
        (props.history
          ? ['verified', 'rejected', 'needs_correction'].includes(row.status)
          : row.status === 'submitted')
    )
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
async function review(row, decision) {
  if (!comments.value[row.id]?.trim()) {
    error.value = '请先填写具体的核验意见。'
    document.getElementById('comment-' + row.id)?.focus()
    return
  }
  busy.value = true
  error.value = ''
  try {
    await materialApi.review(category.value, row.id, row.version, decision, comments.value[row.id])
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
    audit.value[row.id] = (await materialApi.getEvents(category.value, row.id)).events.filter(
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
