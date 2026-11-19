<template>
  <section class="page-content student-materials-hub">
    <div class="page-title"><span>我的材料</span></div>
    <div class="filters primary-section-frame">
      <button class="btn btn-outline" @click="mode = 'competition'">学业竞赛新链路</button>
      <button class="btn btn-outline" @click="router.replace({query:{...route.query,page:'materials',category:'social_practice'}})">其他证书识别与核验</button>
      <button class="btn btn-outline" @click="mode = 'compatibility'">非竞赛兼容记录</button>
    </div>
    <CompetitionWorkflow v-if="mode === 'competition'" />
    <section v-else>
      <p>以下内容来自旧 Application 兼容入口，不会创建竞赛 MaterialRecord。</p>
      <ApplicationHistory @edit-application="$emit('edit-application', $event)" />
    </section>
  </section>
</template>
<script setup>
import { ref } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import CompetitionWorkflow from './CompetitionWorkflow.vue'
import ApplicationHistory from './ApplicationHistory.vue'
defineEmits(['edit-application'])
const mode = ref('competition')
const route=useRoute(),router=useRouter()
</script>
