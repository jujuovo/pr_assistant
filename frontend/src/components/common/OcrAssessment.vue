<template>
  <section class="assessment" aria-label="识别与预估分数">
    <h3>分数预估与材料核对</h3>
    <p
      ><template v-if="!conciseEstimate">如材料属实且与申报信息相符，审核通过后本项</template>预计可得
      <strong>{{ advice?.declared_estimate ?? '暂不可计算' }}</strong> 分。</p
    >
    <p v-if="advice?.job"
      >OCR：{{ jobLabel(advice.job.status) }}
      <span v-if="advice.job.error">{{ advice.job.error }}</span></p
    >
    <template v-if="advice?.job?.status === 'completed'">
      <p
        >OCR 条件性建议分（未识别到的级别及团队信息沿用申报）：<strong>{{
          advice.ocr_suggested_score ?? '依据不足，需人工确认'
        }}</strong></p
      >
      <p>{{
        advice.review_mode === 'rule_assisted'
          ? '已启用规则辅助评分，仍须教师审核。'
          : '此项需教师人工核对后确认计分。'
      }}</p>
      <ul v-if="advice.differences?.length"
        ><li v-for="item in advice.differences" :key="item.field"
          >{{ fieldLabel(item.field) }}不一致：申报“{{ displayValue(item.declared) }}”，识别“{{
            displayValue(item.recognized)
          }}”。</li
        ></ul
      >
      <p v-if="advice.missing_fields?.length"
        >OCR 尚不足以核验：{{ advice.missing_fields.map(fieldLabel).join('、') }}。</p
      >
    </template>
    <small v-if="advice?.job">{{
      advice?.notice || '预估为单项候选分，最终计入分受教师审核、重复项目取舍和加分上限影响。'
    }}</small>
  </section>
</template>
<script setup>
import { fieldLabel, displayValue } from '@/services/materialFields.js'
defineProps({ advice: { type: Object, default: null }, conciseEstimate: Boolean })
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
</style>
