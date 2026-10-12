<template>
  <div class="page-content">
    <div class="page-title">
      <span>系统设置</span>
    </div>

    <!-- 学术年度设置 -->
    <div class="card">
      <div class="card-title">学术年度设置</div>
      <!-- 加载遮罩 -->
      <div v-if="loading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">加载中...</div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">当前学术年度</label>
          <select class="form-control" v-model="settings.academicYear">
            <option v-for="year in academicYearOptions" :key="year.value" :value="year.value">{{
              year.label
            }}</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">申请开始时间</label>
          <input type="datetime-local" class="form-control" v-model="settings.applicationStart" />
        </div>
        <div class="form-group">
          <label class="form-label">申请截止时间</label>
          <input type="datetime-local" class="form-control" v-model="settings.applicationEnd" />
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-outline" @click="saveAcademicSettings">保存设置</button>
      </div>
    </div>

    <!-- 文件存储设置 -->
    <div class="card">
      <div class="card-title">文件存储设置</div>
      <!-- 加载遮罩 -->
      <div v-if="loading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">加载中...</div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">单文件大小限制(MB)</label>
          <input type="number" class="form-control" v-model="settings.singleFileSizeLimit" />
          <div class="help-text">单个上传文件的最大大小</div>
        </div>
        <div class="form-group">
          <label class="form-label">总文件大小限制(MB)</label>
          <input type="number" class="form-control" v-model="settings.totalFileSizeLimit" />
          <div class="help-text">一次申请能上传的所有文件的总大小</div>
        </div>
        <div class="form-group">
          <label class="form-label">头像文件大小限制(MB)</label>
          <input type="number" class="form-control" v-model="settings.avatarFileSizeLimit" />
          <div class="help-text">用户上传头像的最大大小</div>
        </div>
      </div>
      <div class="form-group">
        <label class="form-label">允许的文件类型</label>
        <input type="text" class="form-control" v-model="settings.allowedFileTypes" />
        <div class="help-text">多个扩展名用逗号分隔</div>
      </div>
      <div class="form-actions">
        <button class="btn btn-outline" @click="saveStorageSettings">保存设置</button>
      </div>
    </div>

    <!-- 系统维护 -->
    <div class="card">
      <div class="card-title">系统维护</div>
      <!-- 加载遮罩 -->
      <div v-if="loading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">加载中...</div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">数据库备份</label>
          <button class="btn btn-outline" @click="backupDatabase" :disabled="backupLoading">
            <font-awesome-icon :icon="['fas', 'database']" /> 立即备份
            <span v-if="backupLoading" class="loading-indicator">加载中...</span>
          </button>
          <div class="help-text">上次备份: {{ settings.lastBackup || '从未备份' }}</div>
        </div>
        <div class="form-group">
          <label class="form-label">缓存清理</label>
          <button class="btn btn-outline" @click="clearCache" :disabled="cacheLoading">
            <font-awesome-icon :icon="['fas', 'broom']" /> 清理缓存
            <span v-if="cacheLoading" class="loading-indicator">加载中...</span>
          </button>
          <div class="help-text">清理系统缓存数据</div>
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label class="form-label">系统状态</label>
          <div class="system-status">
            <span :class="`status-indicator ${systemStatus}`"></span>
            {{ systemStatusText }}
            <button class="btn btn-outline" @click="toggleSystemStatus">
              {{ systemStatus === 'online' ? '进入维护模式' : '恢复正常运行' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 备份文件列表 -->
      <div class="card">
        <div class="card-body">
          <div class="card-title">
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>数据库备份列表</span>
              <div style="display: flex; gap: 10px">
                <input
                  type="file"
                  ref="backupUpload"
                  accept=".zip"
                  style="display: none"
                  @change="handleBackupUpload"
                />
                <button
                  class="btn-outline btn"
                  @click="$refs.backupUpload.click()"
                  :disabled="restoreLoading"
                >
                  <font-awesome-icon icon="fa-solid fa-upload" /> 从备份文件中恢复
                </button>
              </div>
            </div>
          </div>

          <!-- 加载状态指示器 -->
          <div v-if="loadingBackups" class="loading-overlay">
            <div class="loading-spinner"></div>
            <div class="loading-text">加载中...</div>
          </div>

          <!-- 备份文件列表 -->
          <div class="table-container">
            <table class="application-table">
              <thead>
                <tr>
                  <th>备份文件名</th>
                  <th>文件大小</th>
                  <th>创建时间</th>
                  <th style="text-align: center">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="backup in backups" :key="backup.name">
                  <td>{{ backup.name }}</td>
                  <td>{{ formatFileSize(backup.size) }}</td>
                  <td>{{ new Date(backup.create_time).toLocaleString('zh-CN') }}</td>
                  <td>
                    <div class="action-buttons">
                      <button
                        class="btn-outline btn small-btn"
                        @click="downloadBackup(backup)"
                        title="下载备份"
                      >
                        <font-awesome-icon icon="fa-solid fa-download" />
                      </button>
                      <button
                        class="btn-outline btn small-btn danger"
                        @click="restoreDatabase(backup)"
                        title="恢复数据库"
                        :disabled="restoreLoading"
                      >
                        <font-awesome-icon icon="fa-solid fa-redo" />
                      </button>
                      <button
                        class="btn-outline btn small-btn danger"
                        @click="deleteBackup(backup)"
                        title="删除备份"
                        :disabled="restoreLoading"
                      >
                        <font-awesome-icon icon="fa-solid fa-trash" />
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 空状态 -->
          <div v-if="!loadingBackups && backups.length === 0" class="no-data">
            <font-awesome-icon :icon="['fas', 'database']" /> 暂无备份文件
          </div>
        </div>
      </div>

      <!-- 日志文件列表 -->
      <div class="card">
        <div class="card-body">
          <h4 class="card-title">系统日志列表</h4>
          <!-- 加载状态指示器 -->
          <div v-if="loadingLogs" class="loading-overlay">
            <div class="loading-spinner"></div>
            <div class="loading-text">加载中...</div>
          </div>

          <!-- 日志文件列表 -->
          <div class="table-container">
            <table class="application-table">
              <thead>
                <tr>
                  <th>日志文件名</th>
                  <th>文件大小</th>
                  <th>创建时间</th>
                  <th style="text-align: center">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="log in logs" :key="log.name">
                  <td>{{ log.name }}</td>
                  <td>{{ formatFileSize(log.size) }}</td>
                  <td>{{ new Date(log.create_time).toLocaleString('zh-CN') }}</td>
                  <td>
                    <div class="action-buttons">
                      <button
                        class="btn-outline btn small-btn"
                        @click="viewLogContent(log)"
                        title="查看日志"
                      >
                        <font-awesome-icon icon="fa-solid fa-eye" />
                      </button>
                      <button
                        class="btn-outline btn small-btn"
                        @click="downloadLog(log)"
                        title="下载日志"
                      >
                        <font-awesome-icon icon="fa-solid fa-download" />
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 空状态 -->
          <div v-if="!loadingLogs && logs.length === 0" class="no-data">
            <font-awesome-icon :icon="['fas', 'file-alt']" /> 暂无日志文件
          </div>
        </div>
      </div>

      <!-- 日志内容查看模态框 -->
      <div v-if="showLogModal" class="modal-overlay" @click="showLogModal = false">
        <div class="modal-content" @click.stop style="overflow-y: auto; min-height: 400px">
          <div class="modal-header">
            <h3>查看日志 {{ selectedLog.name }}</h3>
            <button class="close-btn" @click="showLogModal = false">
              <font-awesome-icon :icon="['fas', 'times']" />
            </button>
          </div>
          <div class="modal-body">
            <!-- 加载状态指示器 -->
            <div v-if="loadingLogs" class="loading-overlay">
              <div class="loading-spinner"></div>
              <div class="loading-text">加载中...</div>
            </div>
            <div v-else>
              <pre style="white-space: pre-wrap; word-wrap: break-word">{{ logContent }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import api from '@/services/api.js'
import { useToastStore } from '@/stores/toast.js'
const toastStore = useToastStore()

// 动态生成学术年度选项（最近5年）
const generateAcademicYearOptions = () => {
  const currentYear = new Date().getFullYear()
  const options = []
  for (let i = currentYear; i >= currentYear - 4; i--) {
    options.push({
      value: String(i),
      label: `${i}-${i + 1}学年`
    })
  }
  return options
}

const academicYearOptions = ref(generateAcademicYearOptions())

const systemStatus = ref('online') // 在线, 维护

const settings = reactive({
  academicYear: '',
  applicationStart: '',
  applicationEnd: '',
  singleFileSizeLimit: '',
  totalFileSizeLimit: '',
  avatarFileSizeLimit: '',
  allowedFileTypes: '',
  lastBackup: ''
})

// 加载状态变量
const loading = ref(false)
const backupLoading = ref(false)
const cacheLoading = ref(false)
const restoreLoading = ref(false)
const loadingBackups = ref(false)

// 备份文件列表
const backups = ref([])

// 日志文件列表
const logs = ref([])
const loadingLogs = ref(false)

// 日志内容查看相关
const showLogModal = ref(false)
const selectedLog = ref({})
const logContent = ref('')
const loadingLogContent = ref(false)

// 方法
// 处理时间格式，确保发送到API的是正确格式，保持用户输入的原始时区
function prepareDateTimeForApi(dateTimeString) {
  if (!dateTimeString) return ''

  try {
    // 确保输入格式正确(YYYY-MM-DDThh:mm)
    if (!dateTimeString.includes('T')) return ''

    // 构造ISO格式，但不进行时区转换
    // 直接在用户输入的时间后面添加时区信息，假设用户输入的是本地时间(UTC+8)
    const isoString = `${dateTimeString}:00+08:00`

    // 验证日期有效性
    const date = new Date(isoString)
    if (isNaN(date.getTime())) return ''

    return isoString
  } catch (error) {
    console.error('日期准备错误:', error)
    return ''
  }
}

const saveAcademicSettings = async () => {
  loading.value = true
  try {
    // 验证时间范围
    if (settings.applicationStart && settings.applicationEnd) {
      const startDate = new Date(settings.applicationStart)
      const endDate = new Date(settings.applicationEnd)

      if (startDate >= endDate) {
        toastStore.error('申请截止时间必须晚于申请开始时间')
        return
      }
    } else if (settings.applicationStart || settings.applicationEnd) {
      toastStore.error('请同时设置申请开始时间和截止时间')
      return
    }

    // 准备发送到API的数据，确保时间格式正确
    const settingsToSave = {
      academicYear: settings.academicYear,
      applicationStart: prepareDateTimeForApi(settings.applicationStart),
      applicationEnd: prepareDateTimeForApi(settings.applicationEnd)
    }

    await api.updateSystemSettings(settingsToSave)
    toastStore.success('设置已保存')

    // 重新加载设置以验证保存结果
    await loadSystemSettings()
  } catch (error) {
    console.error('保存设置失败:', error)
    toastStore.error('保存设置失败')
  } finally {
    loading.value = false
  }
}

const saveStorageSettings = async () => {
  loading.value = true
  try {
    await api.updateSystemSettings({
      singleFileSizeLimit: settings.singleFileSizeLimit,
      totalFileSizeLimit: settings.totalFileSizeLimit,
      avatarFileSizeLimit: settings.avatarFileSizeLimit,
      allowedFileTypes: settings.allowedFileTypes
    })
    toastStore.success('设置已保存')
    // 重新加载设置以验证保存结果
    await loadSystemSettings()
  } catch (error) {
    console.error('保存设置失败:', error)
    toastStore.error('保存设置失败')
  } finally {
    loading.value = false
  }
}

const backupDatabase = async () => {
  backupLoading.value = true
  try {
    // 调用新的备份API端点
    const response = await fetch('/api/system/backup', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    })

    const data = await response.json()

    if (data.success) {
      // 重新获取系统设置以更新备份时间
      await loadSystemSettings()
      // 重新加载备份列表
      await loadBackups()
      toastStore.success('数据库备份完成')
    } else {
      throw new Error(data.message || '备份失败')
    }
  } catch (error) {
    console.error('数据库备份失败:', error)
    toastStore.error('数据库备份失败')
  } finally {
    backupLoading.value = false
  }
}

// 获取备份文件列表
const loadBackups = async () => {
  loadingBackups.value = true
  try {
    const response = await fetch('/api/system/backups')
    const data = await response.json()

    if (data.success) {
      backups.value = data.backups
    } else {
      throw new Error(data.message || '获取备份列表失败')
    }
  } catch (error) {
    console.error('获取备份列表失败:', error)
    toastStore.error('获取备份列表失败')
  } finally {
    loadingBackups.value = false
  }
}

// 获取日志文件列表
const loadLogs = async () => {
  loadingLogs.value = true
  try {
    const response = await fetch('/api/system/logs')
    const data = await response.json()

    if (data.success) {
      logs.value = data.logs
    } else {
      throw new Error(data.message || '获取日志列表失败')
    }
  } catch (error) {
    console.error('获取日志列表失败:', error)
    toastStore.error('获取日志列表失败')
  } finally {
    loadingLogs.value = false
  }
}

// 恢复数据库
const restoreDatabase = async (backup) => {
  if (
    !confirm(
      `确定要从备份文件 ${backup.name} 恢复数据库吗？此操作将覆盖当前数据库中的所有数据，且无法撤销！`
    )
  ) {
    return
  }

  restoreLoading.value = true
  try {
    const response = await fetch('/api/system/restore', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ filename: backup.name })
    })

    const data = await response.json()

    if (data.success) {
      toastStore.success('数据库恢复成功')
    } else {
      throw new Error(data.message || '恢复失败')
    }
  } catch (error) {
    console.error('数据库恢复失败:', error)
    toastStore.error('数据库恢复失败')
  } finally {
    restoreLoading.value = false
  }
}

// 下载备份文件
const downloadBackup = async (backup) => {
  try {
    const response = await fetch(backup.download_url)

    if (!response.ok) {
      throw new Error('下载失败')
    }

    // 获取后端返回的文件名
    const contentDisposition = response.headers.get('content-disposition')
    let filename = backup.name
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?([^;"]+)"?/)
      if (match) {
        filename = match[1]
      }
    }

    // 创建下载链接
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()

    // 清理
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)

    toastStore.success('备份文件下载开始')
  } catch (error) {
    console.error('下载备份文件失败:', error)
    toastStore.error('下载备份文件失败')
  }
}

// 删除备份文件
const deleteBackup = async (backup) => {
  try {
    if (confirm(`确定要删除备份文件 ${backup.name} 吗？此操作将永久删除该备份文件，且无法恢复！`)) {
      const response = await fetch(`/api/system/backup/delete/${backup.name}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        }
      })

      const data = await response.json()

      if (data.success) {
        // 重新加载备份列表
        await loadBackups()
        toastStore.success('备份文件删除成功')
      } else {
        throw new Error(data.message || '删除失败')
      }
    }
  } catch (error) {
    console.error('删除备份文件失败:', error)
    toastStore.error('删除备份文件失败')
  }
}

// 处理备份文件上传
const handleBackupUpload = async (event) => {
  const files = event.target.files
  if (!files || files.length === 0) return

  const formData = new FormData()

  // 检查是否是单个ZIP文件
  if (files.length !== 1 || !files[0].name.endsWith('.zip')) {
    toastStore.error('请上传单个.zip格式的备份文件')
    return
  }

  // 新方式：上传单个ZIP文件
  formData.append('file', files[0])

  if (confirm(`确定要上传并恢复备份吗？此操作将覆盖当前数据库中的所有数据和文件，且无法撤销！`)) {
    restoreLoading.value = true
    try {
      const response = await fetch('/api/system/restore/upload', {
        method: 'POST',
        body: formData
      })

      const data = await response.json()

      if (data.success) {
        // 重新加载备份列表
        await loadBackups()
        toastStore.success('备份恢复成功')
      } else {
        throw new Error(data.message || '恢复失败')
      }
    } catch (error) {
      console.error('上传并恢复备份失败:', error)
      toastStore.error('上传并恢复备份失败')
    } finally {
      restoreLoading.value = false
      // 清空文件输入
      event.target.value = ''
    }
  } else {
    // 清空文件输入
    event.target.value = ''
  }
}

// 格式化文件大小
const formatFileSize = (size) => {
  if (size < 1024) {
    return size + ' B'
  } else if (size < 1024 * 1024) {
    return (size / 1024).toFixed(2) + ' KB'
  } else if (size < 1024 * 1024 * 1024) {
    return (size / (1024 * 1024)).toFixed(2) + ' MB'
  } else {
    return (size / (1024 * 1024 * 1024)).toFixed(2) + ' GB'
  }
}

const viewSystemLogs = async () => {
  await loadLogs()
}

// 下载日志文件
const downloadLog = async (log) => {
  try {
    const response = await fetch(`/api/system/log/download/${log.name}`)

    if (!response.ok) {
      throw new Error('下载失败')
    }

    // 创建下载链接
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = log.name
    document.body.appendChild(a)
    a.click()

    // 清理
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)

    toastStore.success('日志文件下载开始')
  } catch (error) {
    console.error('下载日志文件失败:', error)
    toastStore.error('下载日志文件失败')
  }
}

// 查看日志内容
const viewLogContent = async (log) => {
  selectedLog.value = log
  showLogModal.value = true
  loadingLogContent.value = true

  try {
    const response = await fetch(`/api/system/log/view/${log.name}`)
    const data = await response.json()

    if (data.success) {
      logContent.value = data.content
    } else {
      throw new Error(data.message || '获取日志内容失败')
    }
  } catch (error) {
    console.error('查看日志内容失败:', error)
    toastStore.error('查看日志内容失败')
    logContent.value = '无法加载日志内容：' + error.message
  } finally {
    loadingLogContent.value = false
  }
}

const clearCache = async () => {
  cacheLoading.value = true
  try {
    // 调用新的缓存清理API端点
    const response = await fetch('/api/system/cache/clear', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    })

    const data = await response.json()

    if (data.success) {
      toastStore.success('缓存清理成功')
    } else {
      throw new Error(data.message || '缓存清理失败')
    }
  } catch (error) {
    console.error('清理缓存失败:', error)
    toastStore.error('清理缓存失败')
  } finally {
    cacheLoading.value = false
  }
}

const toggleSystemStatus = async () => {
  loading.value = true
  try {
    if (systemStatus.value === 'online') {
      if (confirm('确定要进入系统维护模式吗？在此期间用户将无法访问系统。')) {
        systemStatus.value = 'maintenance'
        await api.updateSystemSettings({
          systemStatus: systemStatusApiValue.value
        })
        toastStore.success('系统已进入维护模式')
      }
    } else {
      systemStatus.value = 'online'
      await api.updateSystemSettings({
        systemStatus: systemStatusApiValue.value
      })
      toastStore.success('系统已恢复正常运行')
    }
  } catch (error) {
    console.error('切换系统状态失败:', error)
    toastStore.error('切换系统状态失败')
  } finally {
    loading.value = false
  }
}

// 生命周期
onMounted(() => {
  // 加载系统设置
  loadSystemSettings()
  // 加载备份文件列表
  loadBackups()
  // 加载日志文件列表
  loadLogs()
})

// 系统状态文本映射
const systemStatusText = computed(() => {
  return systemStatus.value === 'online' ? '运行正常' : '系统维护中'
})

const systemStatusApiValue = computed(() => {
  return systemStatus.value === 'online' ? '正常' : '维护中'
})

// 格式化日期时间为datetime-local输入框所需格式，正确处理时区
function formatDateTimeForInput(dateTimeString) {
  if (!dateTimeString) return ''

  try {
    const date = new Date(dateTimeString)
    // 检查是否为有效日期
    if (isNaN(date.getTime())) return ''

    // 创建上海时区(UTC+8)的Date对象，确保显示的是本地时间
    // 注意：JavaScript Date对象内部存储为UTC，但这里我们直接格式化显示本地时间
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')

    // 格式化为YYYY-MM-DDThh:mm格式，符合datetime-local输入框要求
    return `${year}-${month}-${day}T${hours}:${minutes}`
  } catch (error) {
    console.error('日期格式化错误:', error)
    return ''
  }
}

// 加载系统设置
async function loadSystemSettings() {
  loading.value = true
  try {
    const response = await api.getSystemSettings()
    const data = response.settings

    // 更新设置数据
    settings.academicYear = data.academicYear || ''
    // 将日期时间格式化为datetime-local输入框所需的格式
    settings.applicationStart = formatDateTimeForInput(data.applicationStart)
    settings.applicationEnd = formatDateTimeForInput(data.applicationEnd)
    settings.singleFileSizeLimit = data.singleFileSizeLimit || ''
    settings.totalFileSizeLimit = data.totalFileSizeLimit || ''
    settings.avatarFileSizeLimit = data.avatarFileSizeLimit || ''
    settings.allowedFileTypes = data.allowedFileTypes || ''
    settings.lastBackup = data.lastBackup || ''

    systemStatus.value = data.systemStatus === '维护中' ? 'maintenance' : 'online'
  } catch (error) {
    console.error('加载系统设置失败:', error)
    toastStore.error('加载系统设置失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped src="@/assets/styles/pages/admin/settings/SystemSettings.css"></style>
