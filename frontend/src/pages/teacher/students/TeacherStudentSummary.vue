<template>
  <section class="page-content teacher-student-summary">
    <div class="page-title"><span>学生竞赛计分汇总（只读）</span></div>
    <div class="filters primary-section-frame">
      <label>学号 <input v-model.trim="studentId" /></label>
      <label>周期 <input v-model.number="year" type="number" min="2000" max="2100" /></label>
      <button class="btn btn-outline" @click="load">查询授权汇总</button>
    </div>
    <p v-if="error" role="alert">{{ error }}</p>
    <table v-if="summary" class="application-table">
      <thead><tr><th>项目</th><th>材料事实</th><th>状态</th><th>候选分</th><th>计入分</th><th>排除原因</th></tr></thead>
      <tbody><tr v-for="item in summary.items" :key="item.record_id">
        <td>{{ item.project_name }}</td><td><pre>{{ JSON.stringify(item.key_facts, null, 2) }}</pre></td>
        <td>{{ item.status }}</td><td>{{ item.candidate_score ?? '-' }}</td>
        <td>{{ item.effective_score ?? '-' }}</td><td>{{ item.exclusion_reason || '-' }}</td>
      </tr></tbody>
    </table>
    <p v-if="summary">该页面不允许编辑材料、规则、候选分或计入分。</p>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import materialApi from '@/services/materialApi.js'
const studentId = ref('')
const year = ref(new Date().getFullYear())
const summary = ref(null)
const error = ref('')
async function load() {
  try { error.value = ''; summary.value = await materialApi.getTeacherCompetitionSummary(studentId.value, year.value) }
  catch (cause) { summary.value = null; error.value = cause.message }
}
</script>
