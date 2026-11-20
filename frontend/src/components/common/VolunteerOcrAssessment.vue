<template>
  <section
    v-if="assessment"
    class="volunteer-assessment"
    :class="{ 'needs-attention': priority }"
    aria-label="志愿服务OCR比对"
  >
    <header
      ><h4>{{ priority ? '申诉材料 · 重点核验' : 'OCR字段核对' }}</h4
      ><span>{{ statusLabel }}</span></header
    >
    <p v-if="priority" class="appeal-reason"><strong>学生申诉理由：</strong>{{ appeal.reason }}</p>
    <p v-if="assessment.status === 'queued'">识别在后台进行，可离开页面继续上传其他材料。</p>
    <p v-if="assessment.status === 'matched'"
      >工时、工时类别和服务记录日期与申报信息一致，正式提交后由教师审核。</p
    >
    <p v-if="assessment.status === 'returned' && !priority"
      >材料已被系统打回。请修改申报后重新识别，或重新上传一份材料；对结果有异议可提出申诉。</p
    >
    <ul v-if="assessment.reasons?.length"
      ><li v-for="reason in assessment.reasons" :key="reason">{{ reason }}</li></ul
    >
    <div v-if="assessment.comparisons?.length" class="table-scroll"
      ><table>
        <thead
          ><tr><th>核对字段</th><th>学生申报</th><th>OCR识别</th><th>结果</th></tr></thead
        >
        <tbody
          ><tr v-for="item in assessment.comparisons" :key="item.field"
            ><th>{{ item.label }}</th
            ><td>{{ item.declared ?? '未填写' }}</td
            ><td>{{ item.recognized ?? '未可靠识别' }}</td
            ><td :class="{ mismatch: !item.matches }">{{
              item.matches
                ? '一致'
                : item.reason === 'missing'
                  ? '未识别，无法核对'
                  : item.reason === 'unreliable'
                    ? '需人工确认'
                    : '不一致或缺失'
            }}</td></tr
          ></tbody
        >
      </table></div
    >
    <details v-if="reports.length"
      ><summary>逐份查看OCR提取结果</summary>
      <article v-for="item in reports" :key="item.job_id"
        ><strong>{{ item.filename }}</strong
        ><p v-if="item.error">{{ item.error }}</p
        ><p v-if="item.report?.platform_policy">{{ item.report.platform_policy.description }}</p
        ><MaterialFacts :data="item.report?.fields || {}" :labels="{ award_date: '服务记录日期' }"
      /></article>
    </details>
    <small>字段一致只表示文字比对通过，材料真实性仍由教师核验。</small>
  </section>
</template>
<script setup>
import { computed } from 'vue'
import MaterialFacts from './MaterialFacts.vue'
const props = defineProps({
  assessment: { type: Object, default: null },
  appeal: { type: Object, default: null },
  priority: Boolean,
  reports: { type: Array, default: () => [] }
})
const statusLabel = computed(
  () =>
    ({ queued: '后台识别中', matched: '字段一致', returned: '已打回', stale: '待重新识别' })[
      props.assessment?.status
    ] || '待识别'
)
</script>
<style scoped>
.volunteer-assessment {
  display: grid;
  gap: 12px;
  padding: 18px;
  background: #f2f7ff;
  border: 1px solid #cddff5;
  border-radius: 12px;
  margin: 14px 0;
}
.volunteer-assessment header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.volunteer-assessment h4,
.volunteer-assessment p,
.volunteer-assessment ul {
  margin: 0;
}
.volunteer-assessment small {
  color: #52667c;
}
.needs-attention {
  background: #fff8e9;
  border: 2px solid #d68a10;
}
.needs-attention h4,
.mismatch {
  color: #a34212;
  font-weight: 700;
}
.appeal-reason {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.table-scroll {
  overflow-x: auto;
}
table {
  border-collapse: collapse;
  width: 100%;
  font-size: 14px;
}
th,
td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid #d8e3ee;
}
</style>
