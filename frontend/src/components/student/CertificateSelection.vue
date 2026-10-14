<template>
  <div class="form-section certificate-selection">
    <div class="section-title">证书识别辅助</div>
    <label class="form-label" for="certificate-project">证书项目</label>
    <select id="certificate-project" class="form-control" :value="project" @change="selectProject($event.target.value)">
      <option value="manual">其他项目 / 完全人工核验</option>
      <option v-for="item in projects" :key="item.key" :value="item.key">{{ item.name }}</option>
    </select>
    <p class="note">{{ project === 'manual' ? '材料直接交由教师人工核验，不计算自动判断置信度。' : '选择图片后后台检查图片质量、水印并识别证书。仅辅助教师核对，不自动认定真实或加分。支持 JPG、PNG、WebP 和最多4页的 PDF。' }}</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p class="note">蓝桥杯材料在选择图片后自动识别；在下方预览表格核对或修改申报值，再正式提交。</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import certificateApi from '@/services/certificateApi.js'
const props = defineProps({ project: { type: String, default: 'manual' }, claims: { type: Object, default: () => ({}) } })
const emit = defineEmits(['update:project', 'update:claims'])
const projects = ref([])
const error = ref('')
const selectProject = (value) => {
  emit('update:project', value)
  if (value === 'manual') emit('update:claims', {})
}
const setClaim = (key, value) => emit('update:claims', { ...props.claims, [key]: value })
onMounted(async () => {
  if (import.meta.env.MODE === 'demo') return
  try { projects.value = (await certificateApi.getCatalog()).projects }
  catch { error.value = '证书库暂时不可用，可使用人工通道提交。' }
})
</script>

<style scoped>
.claim-grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap: 14px; margin-top: 14px; }
.claim-grid label { display: grid; gap: 6px; }
.note { color: #65748a; line-height: 1.65; font-size: 13px; margin: 10px 0; }
.error { color: #b54708; }
</style>
