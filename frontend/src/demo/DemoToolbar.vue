<template>
  <aside class="demo-toolbar">
    <strong>纯前端演示</strong>
    <button v-for="(label, role) in roles" :key="role" @click="enter(role)">{{ label }}</button>
    <button @click="loginPage">登录页</button>
    <button @click="resetDemo">重置示例</button>
  </aside>
</template>
<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import { resetDemo } from '@/demo/mock.js'
const router = useRouter()
const auth = useAuthStore()
const roles = { student: '学生端', teacher: '教师端', admin: '管理员端' }
async function enter(role) {
  await auth.login(`${role}001`, 'demo123', '1234', 'demo')
  await router.push(`/${role}`)
}
async function loginPage() {
  await auth.logout()
  await router.push('/login')
}
</script>
<style scoped src="@/assets/styles/demo/DemoToolbar.css"></style>
