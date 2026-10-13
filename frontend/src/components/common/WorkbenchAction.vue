<template>
  <section class="workbench-action od-row" :aria-label="ariaLabel">
    <svg class="workbench-alert od-fixed" viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <circle cx="32" cy="32" r="28" stroke="currentColor" stroke-width="3" />
      <path d="M32 18v18" stroke="currentColor" stroke-width="6" stroke-linecap="round" />
      <circle cx="32" cy="46" r="3" fill="currentColor" />
    </svg>
    <div class="od-field od-fill">
      <h2>{{ title }}</h2>
      <slot name="description" />
    </div>
    <slot name="action" />
  </section>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    required: true
  },
  ariaLabel: {
    type: String,
    default: '待办事项'
  }
})
</script>
