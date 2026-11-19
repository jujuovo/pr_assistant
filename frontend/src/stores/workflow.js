import { defineStore } from 'pinia'
import { ref } from 'vue'
import workflowApi from '@/services/workflowApi.js'
export const useWorkflowStore = defineStore('workflow', () => {
  const score = ref(null), ranking = ref(null), loading = ref(false), error = ref(null)
  async function run(loader, target) {
    loading.value = true; error.value = null
    try { const value = await loader(); target.value = value; return value }
    catch (reason) { error.value = reason; throw reason }
    finally { loading.value = false }
  }
  const loadScore = (studentId, year) => run(() => workflowApi.getStudentScore(studentId, year), score)
  const loadCurrentScore = studentId => run(() => workflowApi.getCurrentStudentScore(studentId), score)
  const loadRanking = batchId => run(() => workflowApi.getRanking(batchId), ranking)
  return { score, ranking, loading, error, loadScore, loadCurrentScore, loadRanking }
})
