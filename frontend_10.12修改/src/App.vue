<template>
  <div id="app">
    <router-view />
    <!-- 全局Toast组件 -->
    <Toast />
  </div>
</template>

<script setup>
import Toast from '@/components/common/Toast.vue'
</script>

<style src="@/assets/styles/App.css"></style>
