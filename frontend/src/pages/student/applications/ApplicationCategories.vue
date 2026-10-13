<template>
  <section class="application-categories" aria-labelledby="application-categories-title">
    <header class="categories-header">
      <div>
        <p class="categories-kicker">加分申请</p>
        <h1 id="application-categories-title">评测项目</h1>
        <p>请选择评测项目，查看学业成绩或填写对应的申请材料。</p>
      </div>
      <button type="button" class="guide-button" @click="$emit('navigate', 'regulations')">
        <font-awesome-icon :icon="['fas', 'file-lines']" aria-hidden="true" />
        <span>规范指南</span>
      </button>
    </header>

    <div class="category-grid" role="list">
      <button
        v-for="category in categories"
        :key="category.key"
        type="button"
        class="category-button"
        role="listitem"
        @click="$emit('select', category)"
      >
        <span
          class="category-icon"
          :style="{ color: category.color, backgroundColor: category.background }"
        >
          <font-awesome-icon :icon="['fas', category.icon]" aria-hidden="true" />
        </span>
        <strong>{{ category.title }}</strong>
        <span>{{ category.description }}</span>
      </button>
    </div>
  </section>
</template>

<script setup>
defineEmits(['select', 'navigate'])

const categories = [
  {
    key: 'academic-performance',
    title: '学业成绩',
    description: '查看课程成绩与专业排名',
    icon: 'clipboard-list',
    color: '#238a52',
    background: '#e9f7ef'
  },
  {
    key: 'academic-innovation',
    title: '学术创新',
    description: '科研、竞赛及创新成果',
    icon: 'lightbulb',
    color: '#d97706',
    background: '#fff5df'
  },
  {
    key: 'social-work',
    title: '社会工作',
    description: '学生工作及任职经历',
    icon: 'user-group',
    color: '#b77900',
    background: '#fff8dc'
  },
  {
    key: 'volunteer-service',
    title: '志愿服务',
    description: '志愿服务与公益经历',
    icon: 'heart',
    color: '#599b20',
    background: '#eff8e7'
  },
  {
    key: 'social-practice',
    title: '社会实践',
    description: '实践项目及调研成果',
    icon: 'award',
    color: '#149b99',
    background: '#e7f8f7'
  },
  {
    key: 'arts-sports',
    title: '文体活动',
    description: '文化、艺术及体育成果',
    icon: 'trophy',
    color: '#087dcc',
    background: '#e7f4fd'
  }
]
</script>

<style scoped src="@/assets/styles/pages/student/applications/ApplicationCategories.css"></style>
