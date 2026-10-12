import { createRouter, createWebHistory, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'

import Login from '@/pages/common/login/Login.vue'
import Student from '@/pages/student/StudentLayout.vue'
import Teacher from '@/pages/teacher/TeacherLayout.vue'
import Admin from '@/pages/admin/AdminLayout.vue'

const routes = [
  {
    path: '/',
    redirect: import.meta.env.MODE === 'demo' ? '/student' : '/login'
  },
  {
    path: '/login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/student',
    component: Student,
    meta: { requiresAuth: true, role: 'student' }
  },
  {
    path: '/teacher',
    component: Teacher,
    meta: { requiresAuth: true, role: 'teacher' }
  },
  {
    path: '/admin',
    component: Admin,
    meta: { requiresAuth: true, role: 'admin' }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/login'
  }
]

const router = createRouter({
  history: import.meta.env.MODE === 'demo' ? createWebHashHistory() : createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else if (to.meta.role && authStore.role !== to.meta.role) {
    // 如果没有相应角色权限，重定向到登录页
    next('/login')
  } else {
    next()
  }
})

export default router
