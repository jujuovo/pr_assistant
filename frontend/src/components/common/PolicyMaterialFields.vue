<template>
  <div class="policy-fields">
    <label v-for="key in fields" :key="key"
      >{{ labels[key] }}
      <select
        v-if="choices[key]"
        :value="modelValue[key] ?? ''"
        @change="set(key, $event.target.value)"
      >
        <option value="">请选择</option>
        <option v-for="[value, label] in choices[key]" :key="value" :value="value">{{
          label
        }}</option>
      </select>
      <textarea
        v-else-if="lists.includes(key)"
        :value="(modelValue[key] || []).join('\n')"
        placeholder="按顺序填写，每行一人"
        @change="set(key, $event.target.value)"
      />
      <input
        v-else
        :type="key.endsWith('_date') ? 'date' : 'text'"
        :value="modelValue[key]"
        @input="set(key, $event.target.value)"
      />
    </label>
  </div>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ category: String, modelValue: Object, review: Boolean })
const emit = defineEmits(['update:modelValue'])
const common = ['title', 'work_key', 'first_institution', 'authors', 'student_author', 'mentor']
const lists = ['authors', 'cofirst_authors']
const booleanFields = ['completed', 'indexed', 'published', 'authorized_national_invention']
const labels = {
  title: '成果名称',
  work_key: '成果唯一标识',
  first_institution: '第一署名单位',
  authors: '作者或发明人顺序',
  student_author: '学生本人署名',
  mentor: '导师署名（如有）',
  venue: '会议或期刊全称',
  proof_date: '证明日期',
  published: '已发表',
  indexed: '已收录',
  article_type: '文章类型',
  cofirst_authors: '共同第一作者',
  ccf_grade: 'CCF等级',
  directory_basis: '目录认定依据',
  ccf_version: '核验目录版本',
  ccf_entry: '核验目录条目',
  verified_family: '所属子刊系列',
  impact_factor: '影响因子',
  if_year: '影响因子年份',
  authorized_national_invention: '已获国家发明专利授权',
  certificate_date: '授权证书日期',
  project_name: '项目名称',
  project_number: '立项编号',
  level: '立项级别',
  role: '项目角色',
  completed: '已结题',
  proof_type: '结题证明来源',
  completion_date: '结题日期',
  project_key: '核定项目标识',
  identity_basis: '项目关联依据'
}
const choices = {
  ...Object.fromEntries(
    booleanFields.map((key) => [
      key,
      [
        ['true', '是'],
        ['false', '否']
      ]
    ])
  ),
  level: [
    ['national', '国家级'],
    ['provincial', '省级'],
    ['university', '校级']
  ],
  role: [
    ['leader', '负责人'],
    ['member', '成员']
  ],
  proof_type: [
    ['academic_affairs', '教务处证明'],
    ['innovation_portal', '创新网结题截图']
  ],
  article_type: [
    ['long_article', '长文'],
    ['full_article', '正文'],
    ['other', '其他']
  ],
  ccf_grade: ['A', 'B', 'C'].map((v) => [v, v]),
  verified_family: ['Nature', 'Science', 'CELL'].map((v) => [v, v])
}
const fields = computed(() => {
  if (props.category === 'innovation_training')
    return [
      'project_name',
      'project_number',
      'level',
      'role',
      'completed',
      'proof_type',
      'completion_date',
      ...(props.review ? ['project_key', 'identity_basis'] : [])
    ]
  if (props.category === 'invention_patent')
    return [...common, 'authorized_national_invention', 'certificate_date']
  return [
    ...common,
    'venue',
    'proof_date',
    'published',
    'indexed',
    'article_type',
    'cofirst_authors',
    'ccf_grade',
    'directory_basis',
    ...(props.review ? ['ccf_version', 'ccf_entry', 'verified_family'] : []),
    ...(props.modelValue.verified_family === 'CELL' ? ['impact_factor', 'if_year'] : [])
  ]
})
function set(key, raw) {
  const data = { ...props.modelValue }
  if (!raw) delete data[key]
  else if (lists.includes(key))
    data[key] = raw
      .split('\n')
      .map((v) => v.trim())
      .filter(Boolean)
  else if (booleanFields.includes(key)) data[key] = raw === 'true'
  else data[key] = key === 'if_year' ? Number(raw) : raw
  if (props.category === 'research_paper') data.cofirst_authors ||= []
  emit('update:modelValue', data)
}
</script>
<style scoped>
.policy-fields {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
}
label {
  display: grid;
  gap: 5px;
}
input,
select,
textarea {
  padding: 8px;
  border: 1px solid #b9c7d8;
  border-radius: 7px;
}
</style>
