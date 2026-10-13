<template>
  <aside class="student-nav" :class="{ 'is-collapsed': sidebarCollapsed }"
    ><button
      class="sidebar-collapse-toggle"
      :aria-label="sidebarCollapsed ? '展开侧栏' : '收起侧栏'"
      :aria-expanded="!sidebarCollapsed"
      aria-controls="student-side-navigation"
      @click="sidebarCollapsed = !sidebarCollapsed"
      ><svg
        viewBox="0 0 24 24"
        width="20"
        height="20"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <path :d="sidebarCollapsed ? 'M9 6l6 6-6 6' : 'M15 6l-6 6 6 6'" /></svg
      ><span class="collapse-label">收起侧栏</span></button
    ><button
      class="student-identity od-row"
      :class="{ selected: activePage === 'home' }"
      :aria-current="activePage === 'home' ? 'page' : undefined"
      @click="go('home')"
      ><img
        v-if="auth.userAvatar && !avatarFailed"
        :src="auth.userAvatar"
        alt=""
        width="48"
        height="48"
        @error="avatarFailed = true"
      /><span v-else class="identity-fallback" aria-hidden="true">演</span
      ><span class="od-field"
        ><strong>演示同学</strong><span class="identity-role">学生</span></span
      ></button
    ><button class="nav-mobile-toggle" :aria-expanded="mobileOpen" @click="mobileOpen = !mobileOpen"
      >{{ mobileOpen ? '收起导航' : '展开导航' }} · {{ currentLabel }}</button
    ><nav
      id="student-side-navigation"
      :class="{ 'nav-mobile-open': mobileOpen }"
      aria-label="学生导航"
      ><button
        class="student-direct-item"
        :class="{ selected: activePage === 'profile' }"
        :aria-current="activePage === 'profile' ? 'page' : undefined"
        @click="go('profile')"
        ><font-awesome-icon :icon="['fas', 'user']" aria-hidden="true" /><span
          >个人信息</span
        ></button
      ><section v-for="group in groups" :key="group.id" class="student-nav-group"
        ><button
          class="student-group-title"
          :aria-expanded="expanded[group.id]"
          :aria-controls="'group-' + group.id"
          @click="toggle(group)"
          ><span class="nav-title-content"
            ><font-awesome-icon :icon="['fas', group.icon]" aria-hidden="true" /><span>{{
              group.title
            }}</span></span
          ><span aria-hidden="true">{{ expanded[group.id] ? '⌃' : '⌄' }}</span></button
        ><div v-show="expanded[group.id]" :id="'group-' + group.id" class="student-nav-items"
          ><button
            v-for="item in group.items"
            :key="item.key"
            :class="{ selected: activePage === item.key }"
            :aria-current="activePage === item.key ? 'page' : undefined"
            @click="go(item.key)"
            ><font-awesome-icon :icon="['fas', item.icon]" aria-hidden="true" /><span>{{
              item.title
            }}</span></button
          ></div
        ></section
      ></nav
    ></aside
  >
</template>
<script setup>
import { reactive, ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth.js'
const auth = useAuthStore()
const props = defineProps({ activePage: String })
const emit = defineEmits(['page-change'])
const sidebarCollapsed = ref(false)
const mobileOpen = ref(false)
const avatarFailed = ref(false)
const expanded = reactive({ details: true, apply: true })
const groups = [
  {
    id: 'details',
    title: '推免明细',
    icon: 'file-lines',
    items: [
      { key: 'regulations', title: '保研条例', icon: 'book-open' },
      { key: 'statistics', title: '我的项目', icon: 'folder-open' }
    ]
  },
  {
    id: 'apply',
    title: '加分申请',
    icon: 'file-arrow-up',
    items: [
      { key: 'application-form', title: '提交申请', icon: 'file-circle-plus' },
      { key: 'application-record', title: '申请记录', icon: 'clock-rotate-left' },
      { key: 'feedback', title: '反馈入口', icon: 'comment-dots' }
    ]
  }
]
const currentLabel = computed(() =>
  props.activePage === 'home'
    ? '演示同学'
    : props.activePage === 'profile'
      ? '个人信息'
      : groups.flatMap((g) => g.items).find((i) => i.key === props.activePage)?.title || '学生端'
)
function go(key) {
  emit('page-change', key)
  mobileOpen.value = false
}
function toggle(group) {
  expanded[group.id] = !expanded[group.id]
}
</script>
<style scoped src="@/assets/styles/components/student/StudentNavigation.css"></style>
