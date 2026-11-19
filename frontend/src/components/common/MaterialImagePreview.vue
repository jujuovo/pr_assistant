<template>
  <div v-if="items.length" class="material-previews" aria-label="证明原件预览">
    <div v-for="item in items" :key="item.key" class="preview-item">
      <button
        v-if="item.image"
        type="button"
        class="thumbnail"
        :aria-label="'放大预览：' + item.name"
        @click="open(item, $event)"
      >
        <img
          :src="item.url"
          :alt="item.name + ' 缩略图'"
          @load="loaded.add(item.key)"
          @error="failed.add(item.key)"
          :class="{ hidden: failed.has(item.key) }"
        />
        <span v-if="failed.has(item.key)" class="image-state">图片暂不可用，点击重试预览</span>
        <span v-else-if="!loaded.has(item.key)" class="image-state">正在加载预览…</span>
        <span class="thumbnail-name">{{ item.name }}</span
        ><small>点击放大</small>
      </button>
      <span v-else class="document-name">{{ item.name }}（非图片文件）</span>
    </div>
    <Teleport to="body">
      <div v-if="active" class="image-overlay" @click.self="close">
        <section
          role="dialog"
          aria-modal="true"
          aria-label="证明原件大图预览"
          class="image-dialog"
          @keydown.esc.stop.prevent="close"
          @keydown.tab.prevent="closeButton?.focus()"
        >
          <header
            ><span>{{ active.name }}</span
            ><button ref="closeButton" type="button" class="close-preview" @click="close"
              >关闭预览</button
            ></header
          >
          <p v-if="dialogError" role="alert">图片加载失败，请关闭后重新打开预览。</p>
          <img v-else :src="active.url" :alt="active.name + ' 大图'" @error="dialogError = true" />
        </section>
      </div>
    </Teleport>
  </div>
</template>
<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { lockBodyScroll } from '@/services/bodyScrollLock.js'
const props = defineProps({
  files: { type: Array, default: () => [] },
  attachments: { type: Array, default: () => [] }
})
const items = ref([]),
  active = ref(null),
  loaded = ref(new Set()),
  failed = ref(new Set()),
  dialogError = ref(false),
  closeButton = ref(null)
let objectUrls = [],
  trigger = null,
  releaseScroll = null
const isImage = (name) => /\.(png|jpe?g|webp|bmp|tiff?)$/i.test(name || '')
function close() {
  if (!active.value) return
  active.value = null
  releaseScroll?.()
  releaseScroll = null
  const previous = trigger
  trigger = null
  nextTick(() => previous?.isConnected && previous.focus())
}
function cleanup() {
  close()
  objectUrls.forEach((url) => URL.revokeObjectURL(url))
  objectUrls = []
}
watch(
  () => [props.files, props.attachments],
  () => {
    cleanup()
    loaded.value = new Set()
    failed.value = new Set()
    const local = props.files.map((file, index) => {
      const image = isImage(file.name),
        url = image ? URL.createObjectURL(file) : ''
      if (image) objectUrls.push(url)
      return { key: 'local-' + index, name: file.name, image, url }
    })
    const stored = props.attachments.map((file) => ({
      key: 'stored-' + file.id,
      name: file.filename,
      image: isImage(file.filename),
      url: file.url + (file.url?.includes('?') ? '&' : '?') + 'inline=1'
    }))
    items.value = [...stored, ...local]
  },
  { immediate: true }
)
async function open(item, event) {
  if (!active.value) releaseScroll = lockBodyScroll()
  trigger = event.currentTarget
  active.value = item
  dialogError.value = false
  await nextTick()
  closeButton.value?.focus()
}
onBeforeUnmount(cleanup)
</script>
<style scoped>
.material-previews {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 12px;
}
.preview-item {
  min-width: 0;
  max-width: 200px;
}
.thumbnail {
  display: grid;
  position: relative;
  gap: 6px;
  width: 180px;
  padding: 10px;
  border: 1px solid #c6d6e8;
  border-radius: 9px;
  background: #fff;
  cursor: zoom-in;
  text-align: left;
  color: #172033;
}
.thumbnail:hover,
.thumbnail:focus-visible {
  border-color: #0b5cab;
  outline: 2px solid #cde1f6;
}
.thumbnail img {
  width: 158px;
  height: 112px;
  object-fit: contain;
  background: #f3f6fa;
  border-radius: 5px;
}
.thumbnail .hidden {
  visibility: hidden;
}
.thumbnail-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.thumbnail small {
  color: #0b5cab;
}
.image-state {
  position: absolute;
  top: 38px;
  left: 12px;
  right: 12px;
  font-size: 12px;
  text-align: center;
  color: #64748b;
}
.document-name {
  display: block;
  padding: 12px;
  border: 1px solid #dce5ef;
  border-radius: 8px;
  overflow-wrap: anywhere;
}
.image-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.78);
}
.image-dialog {
  max-width: 96vw;
  max-height: 94vh;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 20px 70px #0006;
}
.image-dialog header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  padding: 12px 16px;
}
.image-dialog header span {
  overflow-wrap: anywhere;
}
.image-dialog > img {
  min-height: 0;
  max-width: 94vw;
  max-height: calc(94vh - 64px);
  object-fit: contain;
}
.close-preview {
  flex-shrink: 0;
  min-height: 40px;
  padding: 8px 14px;
  border: 1px solid #b9c7d8;
  border-radius: 7px;
  background: #fff;
  cursor: pointer;
}
.image-dialog p {
  padding: 20px;
}
@media (max-width: 640px) {
  .image-overlay {
    padding: 8px;
  }
  .image-dialog {
    max-width: 98vw;
  }
  .thumbnail {
    width: 150px;
  }
  .thumbnail img {
    width: 128px;
  }
}
</style>
