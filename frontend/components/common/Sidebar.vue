<template>
  <!-- 侧边栏导航（桌面端） -->
  <div class="sidebar-container">
    <aside class="sidebar" :class="{ 'sidebar-collapsed': !isSidebarOpen }">
      <!-- 用户信息区域 - 只在展开时显示 -->
      <div v-if="isSidebarOpen" class="user-info">
        <div class="avatar-wrapper">
          <img :src="userAvatar" alt="用户头像" class="user-avatar">
          <div class="user-status"></div>
        </div>
        <div class="user-details">
          <div class="user-name">{{ currentUser.name }}</div>
          <div class="user-faculty">{{ currentUser.faculty }}</div>
          
          <!-- 学生显示专业，教师/管理员显示角色 -->
          <div v-if="currentUserRole === 'student'" class="user-info-item">
            <font-awesome-icon :icon="['fas', 'graduation-cap']" class="info-icon" />
            <span class="info-text">{{ currentUser.major || '未分配专业' }}</span>
          </div>
          
          <div v-if="currentUserRole === 'teacher'" class="user-info-item">
            <font-awesome-icon :icon="['fas', 'chalkboard-teacher']" class="info-icon" />
            <span class="info-text">教师</span>
          </div>
          
          <div v-if="currentUserRole === 'admin'" class="user-info-item">
            <font-awesome-icon :icon="['fas', 'user-shield']" class="info-icon" />
            <span class="info-text">管理员</span>
          </div>
          
          <!-- 折叠按钮 - 在用户信息区域内 -->
          <button class="collapse-btn" @click="toggleSidebar" title="收起侧边栏">
            <font-awesome-icon :icon="['fas', 'chevron-left']" />
          </button>
        </div>
      </div>
      
      <!-- 展开按钮 - 只在收起时显示 -->
      <div v-if="!isSidebarOpen" class="expand-button-area">
        <button class="expand-btn" @click="toggleSidebar" title="展开侧边栏">
          <font-awesome-icon :icon="['fas', 'chevron-right']" />
        </button>
      </div>

      <!-- 导航菜单 -->
      <nav class="sidebar-nav">
        <ul>
          <li v-for="item in menuItems" 
              :key="item.key" 
              :class="{ active: activePage === item.key }"
              @click="handlePageChange(item.key)">
            <a href="#" @click.prevent>
              <div class="menu-icon-wrapper">
                <font-awesome-icon :icon="item.icon" />
              </div>
              <span class="menu-title">{{ item.title }}</span>
              <div class="active-indicator"></div>
            </a>
          </li>
        </ul>
      </nav>
    </aside>
  </div>
  
  <!-- 移动端顶部导航栏 -->
  <div class="mobile-navigation">
    <!-- 移动端导航选项卡 -->
    <div class="mobile-nav-scroll">
      <div class="mobile-nav-tabs">
        <button 
          v-for="item in menuItems" 
          :key="item.key"
          :class="['mobile-nav-tab', { 'active': activePage === item.key }]"
          @click="handlePageChange(item.key)"
          :title="item.title"
        >
          <font-awesome-icon :icon="item.icon" class="mobile-nav-icon" />
          <span class="mobile-nav-label">{{ item.title }}</span>
          <div class="mobile-tab-indicator" v-if="activePage === item.key"></div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../../stores/auth'

const props = defineProps({
  activePage: String
})

const emit = defineEmits(['page-change', 'sidebar-toggle'])

const authStore = useAuthStore()

const userAvatar = computed(() => authStore.userAvatar)

// 侧边栏展开/收起状态
const isSidebarOpen = ref(true)

// 切换侧边栏展开/收起状态
const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
  emit('sidebar-toggle', isSidebarOpen.value)
}

// 处理页面切换
const handlePageChange = (page) => {
  emit('page-change', page)
}

// 菜单配置
const menuConfig = {
  student: [
    { key: 'application-form', icon: ['fas', 'file-upload'], title: '加分申请' },
    { key: 'application-record', icon: ['fas', 'history'], title: '申请记录' },
    { key: 'statistics', icon: ['fas', 'chart-pie'], title: '加分统计' },
    { key: 'profile', icon: ['fas', 'user'], title: '个人信息' }
  ],
  teacher: [
    { key: 'pending-review', icon: ['fas', 'file-upload'], title: '待审核申请' },
    { key: 'review-history', icon: ['fas', 'history'], title: '审核记录' },
    { key: 'statistics-report', icon: ['fas', 'chart-pie'], title: '统计报表' },
    { key: 'profile', icon: ['fas', 'user'], title: '个人信息' }
  ],
  admin: [
    { key: 'user-management', icon: ['fas', 'users'], title: '用户管理' },
    { key: 'faculty-management', icon: ['fas', 'university'], title: '学院管理' },
    { key: 'data-management', icon: ['fas', 'database'], title: '申请管理' },
    { key: 'score-management', icon: ['fas', 'user-graduate'], title: '成绩管理' },
    { key: 'rule-management', icon: ['fas', 'ruler'], title: '规则管理' },
    { key: 'statistics-report', icon: ['fas', 'chart-pie'], title: '统计报表' },
    { key: 'graduate-file-management', icon: ['fas', 'file-lines'], title: '推免文件管理' },
    { key: 'system-settings', icon: ['fas', 'cog'], title: '系统设置' },
    { key: 'profile', icon: ['fas', 'user'], title: '个人信息' }
  ]
}

// 从auth store获取当前用户角色
const currentUserRole = computed(() => authStore.user?.role || 'student')

// 获取当前用户信息
const currentUser = computed(() => {
  const user = authStore.user || {}
  return {
    name: user.name || '用户',
    faculty: user.faculty || '未分配学院',
    major: user.major || user.majorName || '',
    department: user.department || user.departmentName || '',
    role: user.role || 'student'
  }
})

// 菜单配置
const menuItems = computed(() => menuConfig[currentUserRole.value] || [])
</script>

<style scoped>
.sidebar-container {
  display: flex;
  align-items: stretch;
  position: relative;
  height: 100%;
  min-height: calc(100vh - 60px);
}

.sidebar {
  width: 260px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border-right: 1px solid #e5e7eb;
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 1px 0 10px rgba(0, 0, 0, 0.05);
  position: relative;
  z-index: 1;
}

/* 用户信息区域 */
.user-info {
  display: flex;
  flex-direction: row;
  align-items: center;
  margin-bottom: 14px;
  border-bottom: 1px solid #f1f5f9;
  position: relative;
}

.avatar-wrapper {
  position: relative;
  margin-right: 4px;
  flex-shrink: 0;
}

.user-avatar {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid #ffffff;
  box-shadow: 0 4px 12px rgba(0, 61, 134, 0.15);
  transition: all 0.3s ease;
}

.user-status {
  position: absolute;
  bottom: 5px;
  right: 5px;
  width: 14px;
  height: 14px;
  background: linear-gradient(135deg, #4CAF50, #45a049);
  border-radius: 50%;
  border: 2px solid #ffffff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.user-details {
  text-align: left;
  width: 100%;
  position: relative;
}

.user-name {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-faculty {
  font-size: 14px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 用户信息项 */
.user-info-item {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 13px;
  color: #6b7280;
  margin-top: 6px;
  padding: 4px 10px;
  background: rgba(0, 61, 134, 0.05);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.user-info-item:hover {
  background: rgba(0, 61, 134, 0.1);
}

.info-icon {
  font-size: 12px;
  color: #003d86;
  flex-shrink: 0;
}

.info-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 160px;
}

/* 折叠按钮 - 在用户信息区域内 */
.collapse-btn {
  position: absolute;
  top: 0;
  right: 0;
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  transition: all 0.3s ease;
  z-index: 10;
}

.collapse-btn:hover {
  background: rgba(0, 61, 134, 0.1);
  color: #003d86;
  transform: translateX(-2px);
}

/* 展开按钮区域 - 只在收起时显示 */
.expand-button-area {
  display: flex;
  justify-content: center;
  align-items: center;
  border-bottom: 1px solid #f1f5f9;
  margin-bottom: 20px;
  padding-bottom: 20px;
  height: 90px;
}

.expand-btn {
  width: 50px;
  height: 50px;
  background: transparent;
  border: none;
  border-radius: 12px;
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: all 0.3s ease;
}

.expand-btn:hover {
  background: rgba(0, 61, 134, 0.1);
  color: #003d86;
  transform: translateX(2px);
}

/* 导航菜单 */
.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}

.sidebar-nav::-webkit-scrollbar {
  width: 4px;
}

.sidebar-nav::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar-nav::-webkit-scrollbar-thumb {
  background: #e5e7eb;
  border-radius: 2px;
}

.sidebar-nav::-webkit-scrollbar-thumb:hover {
  background: #d1d5db;
}

.sidebar-nav ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.sidebar-nav li {
  margin-bottom: 4px;
  position: relative;
}

.sidebar-nav li a {
  display: flex;
  align-items: center;
  text-decoration: none;
  color: #4b5563;
  padding: 12px 16px;
  border-radius: 10px;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.menu-icon-wrapper {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
  flex-shrink: 0;
}

.menu-icon-wrapper svg {
  font-size: 16px;
  color: #6b7280;
  transition: all 0.3s ease;
}

.menu-title {
  font-size: 15px;
  font-weight: 500;
  white-space: nowrap;
  transition: all 0.3s ease;
}

.active-indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%) scaleY(0);
  width: 3px;
  height: 60%;
  background: linear-gradient(180deg, #003d86, #0066cc);
  border-radius: 0 3px 3px 0;
  transition: transform 0.3s ease;
}

/* 悬停效果 */
.sidebar-nav li a:hover {
  background: linear-gradient(135deg, rgba(0, 61, 134, 0.05), rgba(0, 102, 204, 0.05));
  color: #003d86;
  transform: translateX(4px);
}

.sidebar-nav li a:hover .menu-icon-wrapper svg {
  color: #023b81;
  transform: scale(1.1);
}

/* 激活状态 */
.sidebar-nav li.active a {
  background: linear-gradient(135deg, #003d86, #0066cc);
  color: white;
  box-shadow: 0 4px 12px rgba(0, 61, 134, 0.25);
}

.sidebar-nav li.active .menu-icon-wrapper svg {
  color: white;
}

.sidebar-nav li.active .active-indicator {
  transform: translateY(-50%) scaleY(1);
}

/* 侧边栏折叠状态 */
.sidebar-collapsed {
  width: 68px;
  padding: 20px 0;
}

/* 收起时隐藏用户信息和菜单文字 */
.sidebar-collapsed .user-info,
.sidebar-collapsed .menu-title {
  display: none;
}

/* 收起时菜单项样式 */
.sidebar-collapsed .sidebar-nav li a {
  justify-content: center;
  padding: 12px 0;
  width: 100%;
  margin: 0 auto;
  border-radius: 8px;
}

.sidebar-collapsed .menu-icon-wrapper {
  margin-right: 0;
  width: 25px;
  height: 25px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sidebar-collapsed .menu-icon-wrapper svg {
  font-size: 16px;
}

/* 收起时的悬停和激活状态 */
.sidebar-collapsed .sidebar-nav li a:hover {
  background: linear-gradient(135deg, rgba(0, 61, 134, 0.08), rgba(0, 102, 204, 0.08));
  transform: none;
}

.sidebar-collapsed .sidebar-nav li.active a {
  background: linear-gradient(135deg, #003d86, #0066cc);
  box-shadow: 0 4px 8px rgba(0, 61, 134, 0.25);
}

.sidebar-collapsed .active-indicator {
  left: 2px;
  width: 2px;
  height: 40%;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .sidebar {
    width: 240px;
  }
  
  .sidebar-collapsed {
    width: 64px;
  }
  
  .user-avatar {
    width: 60px;
    height: 60px;
  }
  
  .user-info {
    padding: 14px;
  }
  
  .avatar-wrapper {
    margin-right: 14px;
  }
  
  .info-text {
    max-width: 120px;
  }
}

/* ==================== 移动端优化样式 ==================== */
.mobile-navigation {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 1000;
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-top: 1px solid rgba(229, 231, 235, 0.8);
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.08);
  padding: 8px 0 12px;
  height: 72px;
}

.mobile-nav-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  -ms-overflow-style: none;
  width: 100%;
  height: 100%;
}

.mobile-nav-scroll::-webkit-scrollbar {
  display: none;
}

.mobile-nav-tabs {
  display: flex;
  width: 100%;
  padding: 0 12px;
  height: 100%;
  align-items: center;
  gap: 4px;
}

.mobile-nav-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 4px;
  background: none;
  border: none;
  border-radius: 12px;
  flex: 1;
  min-width: 0;
  position: relative;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
  touch-action: manipulation;
}

.mobile-nav-tab:active {
  background-color: rgba(0, 61, 134, 0.05);
  transform: scale(0.96);
}

.mobile-nav-icon {
  font-size: 18px;
  color: #6b7280;
  margin-bottom: 4px;
  transition: all 0.2s ease;
  display: block;
}

.mobile-nav-label {
  font-size: 11px;
  color: #6b7280;
  font-weight: 500;
  transition: all 0.2s ease;
  white-space: nowrap;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 激活状态 */
.mobile-nav-tab.active {
  background: linear-gradient(135deg, rgba(0, 61, 134, 0.08), rgba(0, 102, 204, 0.08));
}

.mobile-nav-tab.active .mobile-nav-icon {
  color: #003d86;
  transform: translateY(-2px);
}

.mobile-nav-tab.active .mobile-nav-label {
  color: #003d86;
  font-weight: 600;
}

.mobile-tab-indicator {
  position: absolute;
  top: -4px;
  left: 50%;
  transform: translateX(-50%);
  width: 20px;
  height: 3px;
  background: linear-gradient(135deg, #003d86, #0066cc);
  border-radius: 2px;
  animation: indicatorSlide 0.3s ease;
}

@keyframes indicatorSlide {
  from {
    opacity: 0;
    transform: translateX(-50%) scaleX(0.5);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) scaleX(1);
  }
}

/* 安全区域适配（iPhone X及以上机型） */
@supports (padding-bottom: env(safe-area-inset-bottom)) {
  .mobile-navigation {
    padding-bottom: calc(12px + env(safe-area-inset-bottom));
  }
}

/* 响应式设计 - 移动端隐藏侧边栏，显示底部导航 */
@media (max-width: 768px) {
  .sidebar-container {
    display: none;
  }
  
  .mobile-navigation {
    display: block;
  }
  
  /* 为内容区域添加底部内边距，避免被底部导航遮挡 */
  body {
    padding-bottom: 72px;
  }
}

@media (max-width: 576px) {
  .mobile-nav-tab {
    padding: 6px 4px;
  }
  
  .mobile-nav-icon {
    font-size: 16px;
  }
  
  .mobile-nav-label {
    font-size: 10px;
  }
  
  .mobile-navigation {
    height: 68px;
  }
}

@media (max-width: 375px) {
  .mobile-nav-tab {
    padding: 6px 2px;
  }
  
  .mobile-nav-icon {
    font-size: 15px;
  }
  
  .mobile-nav-label {
    font-size: 9px;
  }
}

/* 在移动设备上完全隐藏侧边栏 */
@media (max-width: 768px) {
  .sidebar-container {
    display: none;
  }
}

@media (max-width: 576px) {
  .sidebar-container {
    display: none;
  }
}

/* 移除旧的顶部导航样式 */
.top-navigation {
  display: none;
}
</style>