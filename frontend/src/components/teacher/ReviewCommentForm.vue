<template>
  <div>
    <label class="material-review-comment" :for="commentId">
      核验意见
      <textarea
        :id="commentId"
        ref="input"
        v-model="comment"
        maxlength="2000"
        :aria-invalid="Boolean(error)"
        :aria-describedby="error ? commentId + '-error' : undefined"
      />
    </label>
    <small v-if="error" :id="commentId + '-error'" class="field-error" role="alert">{{
      error
    }}</small>
    <div class="material-review-actions">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  commentId: { type: String, required: true },
  error: { type: String, default: '' }
})
const comment = defineModel({ type: String })
const input = ref(null)
defineExpose({ focus: () => input.value?.focus() })
</script>

<style scoped>
@import '@/assets/styles/pages/teacher/reviews/MaterialReviewCard.css';

.field-error {
  color: #a12626;
}
</style>
