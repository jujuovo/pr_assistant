<template>
  <section class="home-page"
    ><h1>{{ titles[page] }}</h1>
    <template v-if="page === 'regulations'"
      ><p class="home-subtitle">查看本学院的推免相关文件与申请说明。</p
      ><section class="home-panel student-section-frame"
        ><p v-if="files.loading" role="status">正在获取文件…</p
        ><div v-else-if="files.error" class="home-error"
          >文件加载失败。<button class="home-link" @click="loadFiles">重试</button></div
        ><template v-else
          ><p v-if="!files.files.length">当前暂无公布文件，请稍后查看。</p
          ><article class="home-record" v-for="f in files.files" :key="f.id"
            ><h2>{{ f.filename }}</h2
            ><a class="home-link" :href="getFileFullUrl(f.file_url)" target="_blank" rel="noopener"
              >查看或下载文件</a
            ></article
          ></template
        ></section
      ></template
    >
    <template v-else-if="page === 'feedback'"
      ><p class="home-subtitle">申请或使用过程遇到问题，可先查看审核意见与推免条例。</p
      ><section class="home-panel student-section-frame"
        ><h2>反馈服务尚未接入</h2
        ><p>当前版本暂不支持在线发送反馈。请通过学院已公布的联系渠道咨询，避免重复提交申请。</p
        ><button class="home-link" @click="$emit('navigate', 'regulations')"
          >查看推免条例</button
        ></section
      ></template
    >
  </section>
</template>
<script setup>
import { onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
import { useFilesStore } from '@/stores/files.js'
import { getFileFullUrl } from '@/services/api.js'
const props = defineProps({ page: String })
defineEmits(['navigate'])
const auth = useAuthStore()
const files = useFilesStore()
const titles = {
  regulations: '保研条例',
  feedback: '反馈入口'
}
function loadFiles() {
  files.loadFiles(auth.user?.facultyId || auth.user?.faculty_id)
}
function load() {
  if (props.page === 'regulations') loadFiles()
}
onMounted(load)
watch(() => props.page, load)
</script>
<style scoped src="@/assets/styles/pages/student/home/HomeSections.css"></style>
