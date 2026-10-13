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
    <template v-else
      ><p class="home-subtitle">{{
        page === 'my-forms'
          ? '保存中的申请表单，可继续填写或创建新申请。'
          : '查看需要修改的材料及审核意见，再继续完善申请。'
      }}</p
      ><section class="home-panel" :class="{ 'student-section-frame': page === 'submit-revision' }"
        ><button
          v-if="page === 'my-forms'"
          class="btn btn-primary"
          @click="$emit('navigate', 'application-form')"
          >新建申请</button
        ><p v-if="store.loading" role="status">正在获取申请…</p
        ><div v-else-if="store.error" class="home-error"
          >{{ store.error
          }}<button class="home-link" @click="store.fetchApplications()">重试</button></div
        ><template v-else
          ><p v-if="!rows.length">{{
            page === 'my-forms' ? '暂无草稿。点击新建申请开始填写。' : '当前没有待修改的申请。'
          }}</p
          ><article class="home-record" v-for="a in rows" :key="a.id"
            ><h2>{{ a.projectName || a.eventName || '未命名申请' }}</h2
            ><p>{{ page === 'my-forms' ? '草稿，尚未提交审核' : '待修改' }}</p
            ><p v-if="page === 'submit-revision'"
              >审核意见：{{ a.reviewComment || '暂未提供意见，请联系学院审核人员。' }}</p
            ><button class="home-link" @click="$emit('edit', a.id)">{{
              page === 'my-forms' ? '继续填写' : '修改材料'
            }}</button></article
          ></template
        ><p v-if="page === 'submit-revision'" class="home-note"
          >重新提交需符合申请时间和审核规则；正式提交结果以服务端返回为准。</p
        ></section
      ></template
    >
  </section>
</template>
<script setup>
import { computed, onMounted, watch } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
import { useApplicationsStore } from '@/stores/applications.js'
import { useFilesStore } from '@/stores/files.js'
import { getFileFullUrl } from '@/services/api.js'
const props = defineProps({ page: String })
defineEmits(['navigate', 'edit'])
const auth = useAuthStore()
const store = useApplicationsStore()
const files = useFilesStore()
const titles = {
  regulations: '保研条例',
  'my-forms': '我的表单',
  'submit-revision': '提交修改',
  feedback: '反馈入口'
}
const rows = computed(() =>
  store.applications
    .filter(
      (a) =>
        String(a.studentId || a.student_id) ===
        String(auth.user?.studentId || auth.user?.student_id || auth.user?.username)
    )
    .filter((a) => a.status === (props.page === 'my-forms' ? 'draft' : 'rejected'))
)
function loadFiles() {
  files.loadFiles(auth.user?.facultyId || auth.user?.faculty_id)
}
function load() {
  if (props.page === 'regulations') loadFiles()
  else if (props.page !== 'feedback') store.fetchApplications()
}
onMounted(load)
watch(() => props.page, load)
</script>
<style scoped src="@/assets/styles/pages/student/home/HomeSections.css"></style>
