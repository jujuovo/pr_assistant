<template>
  <div class="review-evidence-grid">
    <section>
      <h4>证明原件</h4>
      <MaterialImagePreview :attachments="attachments" />
      <slot name="attachments" />
    </section>
    <slot />
  </div>
</template>

<script setup>
import MaterialImagePreview from '@/components/common/MaterialImagePreview.vue'

defineProps({ attachments: { type: Array, default: () => [] } })
</script>

<style scoped>
.review-evidence-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
  gap: 16px;
}
.review-evidence-grid > :only-child {
  grid-column: 1 / -1;
}
@media (max-width: 768px) {
  .review-evidence-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
