<template>
  <div class="form-section certificate-selection">
    <div class="section-title">证书识别辅助</div>
    <label class="form-label" for="certificate-project">证书项目</label>
    <select id="certificate-project" class="form-control" :value="project" @change="selectProject($event.target.value)">
      <option value="manual">其他项目 / 完全人工核验</option>
      <option v-for="item in projects" :key="item.key" :value="item.key">{{ item.name }}</option>
    </select>
    <p class="note">{{ project === 'manual' ? '材料直接交由教师人工核验，不计算自动判断置信度。' : '提交后后台检查图片质量、水印并识别证书。仅辅助教师核对，不自动认定真实或加分。支持 JPG、PNG、WebP 和最多4页的 PDF。' }}</p>
    <p v-if="error" class="error">{{ error }}</p>
    <div v-if="project !== 'manual'" class="claim-grid">
      <label>申报获奖等级
        <select class="form-control" :value="claims.award || ''" @change="setClaim('award', $event.target.value)">
          <option value="">请自主选择</option><option>特等奖</option><option>一等奖</option><option>二等奖</option><option>三等奖</option><option>优秀奖</option>
        </select>
      </label>
      <label>申报赛区<input class="form-control" :value="claims.region || ''" maxlength="100" placeholder="如：福建赛区" @input="setClaim('region', $event.target.value)"></label>
      <label>申报组别<input class="form-control" :value="claims.group || ''" maxlength="100" placeholder="如：大学A组" @input="setClaim('group', $event.target.value)"></label>
      <label>申报赛道
        <select class="form-control" :value="claims.track || ''" @change="setClaim('track', $event.target.value)">
          <option value="">请自主选择</option><option>C/C++程序设计</option><option>Python程序设计</option><option>Java程序设计</option><option>C++程序设计</option>
        </select>
      </label>
    </div>
    <p class="note">类别、等级及预计加分仍依据下面自主选择的适用规则和系数计算，最终由教师审核。</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../../utils/api'
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
  try { projects.value = (await api.apiRequest('/certificates/catalog')).projects }
  catch { error.value = '证书库暂时不可用，可使用人工通道提交。' }
})
</script>

<style scoped>
.claim-grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap: 14px; margin-top: 14px; }
.claim-grid label { display: grid; gap: 6px; }
.note { color: #65748a; line-height: 1.65; font-size: 13px; margin: 10px 0; }
.error { color: #b54708; }
</style>
