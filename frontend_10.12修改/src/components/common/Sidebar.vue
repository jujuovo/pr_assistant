<template>
  <div class="sidebar-container role-sidebar-container">
    <aside class="sidebar role-sidebar" :class="{ 'is-collapsed': !isSidebarOpen }">
      <button
        class="role-collapse-toggle"
        :aria-label="isSidebarOpen ? '收起侧栏' : '展开侧栏'"
        :aria-expanded="isSidebarOpen"
        @click="toggleSidebar"
      >
        <font-awesome-icon :icon="['fas', isSidebarOpen ? 'chevron-left' : 'chevron-right']" />
        <span v-if="isSidebarOpen">收起侧栏</span>
      </button>

      <button
        v-if="isSidebarOpen"
        class="role-identity"
        :class="{ selected: activePage === 'home' }"
        :aria-current="activePage === 'home' ? 'page' : undefined"
        @click="handlePageChange('home')"
      >
        <img
          v-if="userAvatar && !avatarFailed"
          :src="userAvatar"
          alt=""
          width="56"
          height="56"
          @error="avatarFailed = true"
        />
        <span v-else class="role-identity-fallback" aria-hidden="true">{{ roleMark }}</span>
        <span class="role-identity-copy"
          ><strong>{{ identityName }}</strong
          ><span>{{ roleLabel }}</span></span
        >
      </button>

      <nav v-if="isSidebarOpen" class="role-navigation" :aria-label="`${roleLabel}导航`">
        <button
          v-for="item in menuItems"
          :key="item.key"
          class="role-menu-item"
          :class="{ selected: activePage === item.key }"
          :aria-current="activePage === item.key ? 'page' : undefined"
          @click="handlePageChange(item.key)"
        >
          <font-awesome-icon :icon="item.icon" aria-hidden="true" />
          <span>{{ item.title }}</span>
        </button>
      </nav>
    </aside>
  </div>

  <nav class="role-mobile-navigation" :aria-label="`${roleLabel}移动端导航`">
    <button :class="{ selected: activePage === 'home' }" @click="handlePageChange('home')"
      ><font-awesome-icon :icon="['fas', 'house']" aria-hidden="true" /><span>{{
        identityName
      }}</span></button
    >
    <button
      v-for="item in menuItems"
      :key="item.key"
      :class="{ selected: activePage === item.key }"
      @click="handlePageChange(item.key)"
      ><font-awesome-icon :icon="item.icon" aria-hidden="true" /><span>{{
        item.title
      }}</span></button
    >
  </nav>
</template>

<script setup>
import { computed, ref } from 'vue'
import { roleNavigation } from '@/config/navigation.js'
import { useAuthStore } from '@/stores/auth.js'

const props = defineProps({ activePage: String })
const emit = defineEmits(['page-change', 'sidebar-toggle'])
const authStore = useAuthStore()
const isSidebarOpen = ref(true)
const avatarFailed = ref(false)
const currentUserRole = computed(() => (authStore.user?.role === 'admin' ? 'admin' : 'teacher'))
const identityName = computed(() =>
  currentUserRole.value === 'teacher' ? '演示教师' : '演示管理员'
)
const roleLabel = computed(() => (currentUserRole.value === 'teacher' ? '教师' : '管理员'))
const roleMark = computed(() => (currentUserRole.value === 'teacher' ? '师' : '管'))
const userAvatar = computed(() => authStore.userAvatar)

const menuItems = computed(() => roleNavigation[currentUserRole.value])
function toggleSidebar() {
  isSidebarOpen.value = !isSidebarOpen.value
  emit('sidebar-toggle', isSidebarOpen.value)
}
function handlePageChange(page) {
  emit('page-change', page)
}
</script>

<style scoped src="@/assets/styles/components/common/Sidebar.css"></style>
