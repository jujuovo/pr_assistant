<template>
  <div class="page-content teacher-review-page">
    <div class="page-title">
      <h1>{{ history ? '审核记录' : '待审核申请' }}</h1>
    </div>
    <details v-for="group in groups" :key="group.label" class="request-group">
      <summary class="request-group-header">
        <span class="request-group-title">{{ group.label }}</span>
        <span v-if="!history" class="request-group-count">{{ groupStatus(group.keys) }}</span>
      </summary>
      <div class="request-group-body">
        <form v-if="history" class="review-student-filter" @submit.prevent="setKeyword(group, inputs[group.keys[0]]?.trim() || '')">
          <label :for="'history-student-' + group.keys[0]">搜索审核记录</label>
          <input :id="'history-student-' + group.keys[0]" v-model="inputs[group.keys[0]]" class="form-control" type="search" placeholder="学号、后四位或材料名称" @input="clearKeyword(group, $event)" />
          <button class="btn btn-outline" type="submit">查看汇总</button>
        </form>
        <p v-if="history && filters[group.keys[0]] && group.keys.every(key => counts[key] === 0)"
          class="review-category-empty" role="status">本栏目暂无匹配的审核记录。</p>
        <section v-for="key in group.keys" v-show="!history || !filters[group.keys[0]] || counts[key] !== 0"
          :key="key" class="review-category">
          <h2 v-if="group.keys.length > 1 || key === 'certification'">{{ categoryLabels[key] }}</h2>
          <TeacherCompetitionReview v-if="key === 'competition'" :mode="history ? 'history' : 'pending'" :keyword="filters[group.keys[0]]" @pending-count="counts[key] = $event" />
          <ManualMaterialReview v-else :fixed-category="key" :history="history" :keyword="filters[group.keys[0]]" compare-evidence @pending-count="counts[key] = $event" />
        </section>
      </div>
    </details>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import ManualMaterialReview from '@/components/common/ManualMaterialReview.vue'
import { manualReviewCategories } from '@/services/teacherReviewCategories.js'
import TeacherCompetitionReview from './TeacherCompetitionReview.vue'

defineProps({ history: Boolean })
const inputs = reactive({})
const filters = reactive({})

function setKeyword(group, studentId) {
  const key = group.keys[0]
  if ((filters[key] ?? '') === studentId) return
  for (const category of group.keys) delete counts[category]
  filters[key] = studentId
}

function clearKeyword(group, event) {
  if (!event.target.value.trim()) setKeyword(group, '')
}

const groups = [
  { label: '竞赛', keys: ['competition', 'competition_evidence'] },
  { label: '志愿服务与社会实践', keys: ['volunteer', 'social_practice'] },
  { label: '论文专利与创业创新', keys: ['research', 'research_paper', 'invention_patent', 'innovation_training'] },
  { label: '学生工作与文体活动', keys: ['student_work', 'arts_sports'] },
  { label: '其他', keys: ['certification'] },
]
const categoryLabels = Object.fromEntries([['competition', '目录内竞赛'], ...manualReviewCategories])
const counts = reactive({})

function groupStatus(keys) {
  const values = keys.map(key => counts[key])
  const total = values.reduce((sum, count) => sum + (count ?? 0), 0)
  const countLabel = total > 0 ? `${total} 件待审核` : ''
  if (values.includes(null)) return [countLabel, '加载失败'].filter(Boolean).join(' · ')
  if (values.includes(undefined)) return '加载中'
  return countLabel || '暂无待审核'
}
</script>

<style scoped src="@/assets/styles/pages/teacher/reviews/PendingReview.css"></style>
