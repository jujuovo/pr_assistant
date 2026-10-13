<template>
  <header class="workbench-welcome">
    <h1>{{ greeting }}，{{ name }}</h1>
    <p>{{ subtitle }}</p>
  </header>
</template>

<script setup>
import { useGreeting } from '@/composables/useGreeting.js'

defineProps({
  name: { type: String, required: true },
  subtitle: { type: String, required: true }
})

const greeting = useGreeting()
</script>
