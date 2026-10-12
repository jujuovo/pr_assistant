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
import { useAuthStore } from '../stores/auth'
import { resetDemo } from './mock'
const router = useRouter()
const auth = useAuthStore()
const roles = { student: '学生端', teacher: '教师端', admin: '管理员端' }
async function enter(role) { await auth.login(`${role}001`, 'demo123', '1234', 'demo'); await router.push(`/${role}`) }
async function loginPage() { await auth.logout(); await router.push('/login') }
</script>
<style scoped>
.demo-toolbar { position: fixed; bottom: 10px; right: 16px; z-index: 10000; display: flex; gap: 6px; align-items: center; padding: 8px 12px; border: 1px solid #c7d2fe; border-radius: 12px; background: #fff; box-shadow: 0 3px 15px #0002; font: 12px sans-serif; }
.demo-toolbar strong { color: #4338ca; }
.demo-toolbar button { padding: 6px 9px; background: #eef2ff; color: #3730a3; border: 0; border-radius: 6px; cursor: pointer; }
</style>
