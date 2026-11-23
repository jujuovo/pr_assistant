<template>
  <section class="assessment" aria-label="识别与预估分数">
    <h3>分数预估与材料核对</h3>
    <template v-if="conciseEstimate">
      <dl class="score-comparison">
        <div class="score-card">
          <dt>申请分数</dt>
          <dd><strong v-if="hasScore(advice?.declared_estimate)">{{ advice.declared_estimate }}</strong>
            <span v-else class="score-unavailable">暂不可计算</span>
            <span v-if="hasScore(advice?.declared_estimate)" class="score-unit">分</span></dd>
        </div>
        <div class="score-card">
          <dt>系统建议分数</dt>
          <dd><strong v-if="advice?.job?.status === 'completed' && hasScore(advice?.ocr_suggested_score)">{{ advice.ocr_suggested_score }}</strong>
            <span v-else class="score-unavailable">{{ suggestionPlaceholder }}</span>
            <span v-if="advice?.job?.status === 'completed' && hasScore(advice?.ocr_suggested_score)" class="score-unit">分</span></dd>
        </div>
      </dl>
      <p v-if="readyToSubmit" class="submission-guidance">请核对分数及下方申报信息与原件，确认无误后点击“正式提交审核”。</p>
      <p v-else-if="['queued', 'running'].includes(advice?.job?.status)" class="submission-guidance">材料正在识别，可稍后返回查看。</p>
      <p v-if="advice?.job?.status === 'failed'" class="submission-guidance">识别失败，请重新识别或提交教师人工核验。</p>
      <small>系统建议分数仅供核对，最终得分以教师审核结果为准。</small>
    </template>
    <template v-else>
      <p>如材料属实且与申报信息相符，审核通过后本项预计可得 <strong>{{ advice?.declared_estimate ?? '暂不可计算' }}</strong> 分。</p>
      <p v-if="advice?.job">OCR：{{ jobLabel(advice.job.status) }} <span v-if="advice.job.error">{{ advice.job.error }}</span></p>
      <template v-if="advice?.job?.status === 'completed'">
        <p>OCR 条件性建议分（未识别到的级别及团队信息沿用申报）：<strong>{{ advice.ocr_suggested_score ?? '依据不足，需人工确认' }}</strong></p>
        <p>{{ advice.review_mode === 'rule_assisted' ? '已启用规则辅助评分，仍须教师审核。' : '此项需教师人工核对后确认计分。' }}</p>
        <p v-if="advice.missing_fields?.length">OCR 尚不足以核验：{{ advice.missing_fields.map(fieldLabel).join('、') }}。</p>
      </template>
      <small v-if="advice?.job">{{ advice.notice || '预估为单项候选分，最终计入分受教师审核、重复项目取舍和加分上限影响。' }}</small>
    </template>
    <ul v-if="advice?.job?.status === 'completed' && advice.differences?.length" class="difference-list" aria-label="申报与识别不一致的字段">
      <li v-for="item in advice.differences" :key="item.field">
        <strong>{{ fieldLabel(item.field) }}不一致</strong>：申报“{{ displayValue(item.declared) }}”，识别“{{ displayValue(item.recognized) }}”。
      </li>
    </ul>
  </section>
</template>
<script setup>
import { computed } from 'vue'
import { fieldLabel, displayValue } from '@/services/materialFields.js'
const props = defineProps({ advice: { type: Object, default: null }, conciseEstimate: Boolean, readyToSubmit: Boolean })
const hasScore = (value) => value !== null && value !== undefined && value !== ''
const suggestionPlaceholder = computed(() => {
  const status = props.advice?.job?.status
  if (['queued', 'running'].includes(status)) return '识别完成后显示'
  if (status === 'completed') return '需人工核验'
  return '暂无建议分数'
})
const jobLabel = (v) =>
  ({
    queued: '队列中，可离开页面',
    running: '识别中，可离开页面',
    completed: '已完成',
    failed: '识别失败，可重试或人工核验',
    stale: '材料已修改，原识别结果已隔离',
    cancelled: '已取消',
    ignored: '旧结果已隔离'
  })[v] || '等待处理'
</script>
<style scoped>
.assessment {
  padding: 18px;
  border: 1px solid #c8d9ec;
  border-radius: 10px;
  background: #f5f9ff;
}
.assessment h3 {
  margin: 0 0 12px;
}
.assessment p {
  line-height: 1.65;
}
.assessment strong {
  color: #0b5cab;
}
.assessment small {
  color: #64748b;
}

.score-comparison {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin: 0 0 16px;
}
.score-card { padding: 16px 20px; border: 1px solid #d6e4f4; border-radius: 10px; background: #fff; }
.score-card dt { color: #40566e; font-weight: 600; }
.score-card dd { margin: 8px 0 0; display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
.score-card strong { font-size: clamp(28px, 3vw, 38px); line-height: 1.2; font-variant-numeric: tabular-nums; }
.score-unit, .score-unavailable { color: #536479; }
.score-unavailable { font-size: 18px; }
.submission-guidance { margin: 12px 0 8px; color: #173d63; font-weight: 600; }
.assessment .difference-list, .assessment .difference-list strong { color: #b42335; }
.difference-list { margin: 16px 0 0; padding: 12px 16px 12px 34px; border-left: 3px solid #b42335; border-radius: 6px; background: #fff0f2; }
.difference-list li + li { margin-top: 8px; }
@media (max-width: 550px) { .score-comparison { grid-template-columns: 1fr; } }
</style>
