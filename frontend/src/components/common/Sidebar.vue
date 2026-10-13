<template>
  <aside class="student-nav" :class="{ 'is-collapsed': !isSidebarOpen }">
    <button
      class="sidebar-collapse-toggle"
      :aria-label="isSidebarOpen ? '收起侧栏' : '展开侧栏'"
      :aria-expanded="isSidebarOpen"
      :aria-controls="navigationId"
      @click="toggleSidebar"
    >
      <svg
        viewBox="0 0 24 24"
        width="20"
        height="20"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <path :d="isSidebarOpen ? 'M15 6l-6 6 6 6' : 'M9 6l6 6-6 6'" />
      </svg>
      <span class="collapse-label">收起侧栏</span>
    </button>

    <button
      class="student-identity od-row"
      :class="{ selected: activePage === 'home' }"
      :aria-current="activePage === 'home' ? 'page' : undefined"
      @click="handlePageChange('home')"
    >
      <img
        v-if="userAvatar && !avatarFailed"
        :src="userAvatar"
        alt=""
        width="48"
        height="48"
        @error="avatarFailed = true"
      />
      <span v-else class="identity-fallback" aria-hidden="true">{{ roleMark }}</span>
      <span class="od-field">
        <strong>{{ identityName }}</strong>
        <span class="identity-role">{{ roleLabel }}</span>
      </span>
    </button>

    <button
      class="nav-mobile-toggle"
      :aria-expanded="mobileOpen"
      :aria-controls="navigationId"
      @click="mobileOpen = !mobileOpen"
    >
      {{ mobileOpen ? '收起导航' : '展开导航' }} · {{ currentLabel }}
    </button>

    <nav
      :id="navigationId"
      :class="{ 'nav-mobile-open': mobileOpen }"
      :aria-label="`${roleLabel}导航`"
    >
      <template v-for="item in navigation" :key="item.key || item.id">
        <button
          v-if="item.key"
          class="student-direct-item"
          :class="{ selected: activePage === item.key }"
          :aria-current="activePage === item.key ? 'page' : undefined"
          @click="handlePageChange(item.key)"
        >
          <font-awesome-icon :icon="['fas', item.icon]" aria-hidden="true" />
          <span>{{ item.title }}</span>
        </button>

        <section v-else class="student-nav-group">
          <button
            class="student-group-title"
            :aria-expanded="expanded[item.id]"
            :aria-controls="`${navigationId}-${item.id}`"
            @click="toggleGroup(item.id)"
          >
            <span class="nav-title-content">
              <font-awesome-icon :icon="['fas', item.icon]" aria-hidden="true" />
              <span>{{ item.title }}</span>
            </span>
            <span aria-hidden="true">{{ expanded[item.id] ? '⌃' : '⌄' }}</span>
          </button>
          <div
            v-show="expanded[item.id]"
            :id="`${navigationId}-${item.id}`"
            class="student-nav-items"
          >
            <button
              v-for="child in item.items"
              :key="child.key"
              :class="{ selected: activePage === child.key }"
              :aria-current="activePage === child.key ? 'page' : undefined"
              @click="handlePageChange(child.key)"
            >
              <font-awesome-icon :icon="['fas', child.icon]" aria-hidden="true" />
              <span>{{ child.title }}</span>
            </button>
          </div>
        </section>
      </template>
    </nav>
  </aside>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { roleNavigation } from '@/config/navigation.js'
import { useAuthStore } from '@/stores/auth.js'

const props = defineProps({ activePage: String })
const emit = defineEmits(['page-change', 'sidebar-toggle'])
const authStore = useAuthStore()
const isSidebarOpen = ref(true)
const mobileOpen = ref(false)
const avatarFailed = ref(false)
const expanded = reactive({
  'recommendation-review': true,
  'recommendation-management': true,
  'recommendation-statistics': true,
  'system-management': true
})

const currentUserRole = computed(() => (authStore.user?.role === 'admin' ? 'admin' : 'teacher'))
const navigation = computed(() => roleNavigation[currentUserRole.value])
const identityName = computed(() =>
  currentUserRole.value === 'teacher' ? '演示教师' : '演示管理员'
)
const roleLabel = computed(() => (currentUserRole.value === 'teacher' ? '教师' : '管理员'))
const roleMark = computed(() => (currentUserRole.value === 'teacher' ? '师' : '管'))
const userAvatar = computed(() => authStore.userAvatar)
const navigationId = computed(() => `${currentUserRole.value}-side-navigation`)
const currentLabel = computed(() => {
  if (props.activePage === 'home') return identityName.value
  return (
    navigation.value
      .flatMap((item) => (item.items ? item.items : [item]))
      .find((item) => item.key === props.activePage)?.title || roleLabel.value
  )
})

function toggleSidebar() {
  isSidebarOpen.value = !isSidebarOpen.value
  emit('sidebar-toggle', isSidebarOpen.value)
}

function toggleGroup(id) {
  expanded[id] = !expanded[id]
}

function handlePageChange(page) {
  emit('page-change', page)
  mobileOpen.value = false
}
</script>

<style scoped src="@/assets/styles/components/student/StudentNavigation.css"></style>
