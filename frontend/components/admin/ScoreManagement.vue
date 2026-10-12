<template>
  <div class="page-content">
    <!-- 页面标题 -->
    <div class="page-title">
      <span>成绩管理</span>
    </div>

    <!-- 模块一：学院综合成绩比例设置 -->
    <div class="card">
      <!-- 加载状态指示器 -->
      <div v-if="loading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">加载中...</div>
      </div>
      <div class="card-title">
        <h3>学院综合成绩比例设置</h3>
      </div>
      <div class="card-body">
        <div class="card-body">
          <!-- 学院搜索框 -->
          <div class="filters">
            <div class="filter-group">
              <span class="filter-label">学院名称:</span>
              <input type="text" class="form-control small" v-model="scoreSettingsSearch" placeholder="输入学院名称">
            </div>
          </div>
          <!-- 成绩设置表格 -->
          <div class="table-container">
            <table class="application-table">
              <thead>
                <tr>
                  <th>学院名称</th>
                  <th>学业成绩比例(%)</th>
                  <th>学术专长上限</th>
                  <th>综合表现上限</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="setting in filteredScoreSettings" :key="setting.faculty_id">
                  <td>{{ getFacultyName(setting.faculty_id) }}</td>
                  <td>{{ setting.academic_score_weight }}</td>
                  <td>{{ setting.specialty_max_score }}</td>
                  <td>{{ setting.performance_max_score }}</td>
                  <td>
                    <div class="action-buttons">
                      <button class="btn-outline btn small-btn" @click="openScoreSettingsDialog(setting)">
                        <font-awesome-icon :icon="['fas', 'edit']"/>
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- 模块二：成绩管理与筛选 -->
    <div class="card">
      <!-- 加载状态指示器 -->
      <div v-if="loading" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">加载中...</div>
      </div>
      <div class="card-title">
        <h3>学生成绩管理</h3>
      </div>
      <div class="card-body">
        <!-- 筛选和搜索区域 -->
        <div class="filters">
          <div class="filter-group">
            <span class="filter-label">姓名:</span>
            <input type="text" class="form-control small" v-model="filters.studentName" placeholder="输入学生姓名">
          </div>
          <div class="filter-group">
            <span class="filter-label">学号:</span>
            <input type="text" class="form-control small" v-model="filters.studentId" placeholder="输入学生学号">
          </div>
          <div class="filter-group">
            <span class="filter-label">当前学院:</span>
            <select class="form-control small" v-model="filters.faculty" @change="onFacultyChange">
              <option value="all">全部学院</option>
              <option v-for="faculty in faculties" :key="faculty.id" :value="faculty.id">
                {{ faculty.name }}
              </option>
            </select>
          </div>
          <div class="filter-group">
            <span class="filter-label">系:</span>
            <select class="form-control small" v-model="filters.department" @change="onDepartmentChange">
              <option value="all">全部系</option>
              <option v-for="dept in departments" :key="dept.id" :value="dept.id">
                {{ dept.name }}
              </option>
            </select>
          </div>
          <div class="filter-group">
            <span class="filter-label">专业:</span>
            <select class="form-control small" v-model="filters.major">
              <option value="all">全部专业</option>
              <option v-for="major in majors" :key="major.id" :value="major.id">
                {{ major.name }}
              </option>
            </select>
          </div>
          <div class="filter-group">
            <button class="btn btn-outline" @click="resetFilter">清空筛选</button>
          </div>
          <div class="filter-group">
            <button class="btn btn-outline" @click="recalculateComprehensiveScores">
              <font-awesome-icon :icon="['fas', 'calculator']" class="me-1" /> 重新计算综合成绩
            </button>
          </div>
        </div>

        <!-- 成绩表格 -->
        <div class="table-container">
          <table class="application-table">
            <thead>
              <tr>
                <th>学号</th>
                <th>姓名</th>
                <th>CET4成绩</th>
                <th>CET6成绩</th>
                <th>GPA</th>
                <th>学业成绩</th>
                <th>学术专长</th>
                <th>综合表现</th>
                <th>考核总分</th>
                <th>综合成绩</th>
                <th>专业排名</th>
                <th>排名人数</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="student in paginatedScores" :key="student.id">
                <td>{{ student.student_id }}</td>
                <td>{{ student.student_name }}</td>
                <td>{{ student.cet4_score || '-' }}</td>
                <td>{{ student.cet6_score || '-' }}</td>
                <td>{{ student.gpa ? student.gpa.toFixed(4) : '-' }}</td>
                <td>{{ student.academic_score ? student.academic_score.toFixed(4) : '-' }}</td>
                <td>{{ student.academic_specialty_total || '-' }}</td>
                <td>{{ student.comprehensive_performance_total || '-' }}</td>
                <td>{{ student.total_score || '-' }}</td>
                <td>{{ student.comprehensive_score || '-' }}</td>
                <td>{{ student.major_ranking || '-' }}</td>
                <td>{{ student.total_students || '-' }}</td>
                <td>
                  <div class="action-buttons">
                    <button class="btn-outline btn small-btn" @click="openEditModal(student)">
                      <font-awesome-icon :icon="['fas', 'edit']" />
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="paginatedScores.length === 0">
                <td :colspan="14" class="no-data">暂无成绩数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      
      <!-- 分页控件 -->
      <div class="pagination">
        <div class="pagination-info">显示 {{ startIndex + 1 }}-{{ endIndex }} 条，共 {{ total }} 条记录</div>
        <div class="pagination-controls">
          <button class="btn-outline btn" :disabled="currentPage === 1" @click="prevPage">
            <font-awesome-icon :icon="['fas', 'chevron-left']" /> 上一页
          </button>
          <button class="btn-outline btn" :disabled="currentPage >= totalPages" @click="nextPage">
            下一页 <font-awesome-icon :icon="['fas', 'chevron-right']" />
          </button>
        </div>
      </div>

      <!-- 添加/编辑学生模态框 -->
      <div v-if="dialogVisible" class="modal-overlay" @click="dialogVisible = false">
        <div class="modal-content" @click.stop>
          <div class="modal-header">
            <h3>编辑成绩</h3>
            <button class="close-btn" @click="dialogVisible = false">
              <font-awesome-icon :icon="['fas', 'times']" />
            </button>
          </div>
          <div class="modal-body">
            <form @submit.prevent="handleSubmit">
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">学号</label>
                  <input type="text" class="form-control" v-model="formData.student_id" disabled />
                </div>
                <div class="form-group">
                  <label class="form-label">姓名</label>
                  <input type="text" class="form-control" v-model="formData.student_name" disabled />
                </div>
              </div>
              <div class="form-row"> 
                <div class="form-group">
                  <label class="form-label">学院</label>
                  <input type="text" class="form-control" :value="formData.facultyName" disabled />
                </div>
                <div class="form-group">
                  <label class="form-label">系</label>
                  <input type="text" class="form-control" :value="formData.departmentName" disabled />
                </div>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">专业</label>
                  <input type="text" class="form-control" :value="formData.majorName" disabled />
                </div>
                <div class="form-group">
                  <label class="form-label">性别</label>
                  <select class="form-control" v-model="formData.gender" placeholder="请选择性别">
                    <option value="">请选择性别</option>
                    <option value="男">男</option>
                    <option value="女">女</option>
                  </select>
                  <div v-if="errors.gender" class="error-message">{{ errors.gender }}</div>
                </div>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">CET4成绩</label>
                  <input type="number" class="form-control" v-model="formData.cet4_score" placeholder="请输入CET4成绩"
                    min="0" max="710" step="1" />
                  <div v-if="errors.cet4_score" class="error-message">{{ errors.cet4_score }}</div>
                </div>
                <div class="form-group">
                  <label class="form-label">CET6成绩</label>
                  <input type="number" class="form-control" v-model="formData.cet6_score" placeholder="请输入CET6成绩"
                    min="0" max="710" step="1" />
                  <div v-if="errors.cet6_score" class="error-message">{{ errors.cet6_score }}</div>
                </div>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">GPA</label>
                  <input type="number" class="form-control" v-model="formData.gpa" placeholder="请输入GPA" min="0" max="4"
                    step="0.0001" />
                  <div v-if="errors.gpa" class="error-message">{{ errors.gpa }}</div>
                </div>
                <div class="form-group">
                  <label class="form-label">学业成绩</label>
                  <input type="number" class="form-control" v-model="formData.academic_score" placeholder="请输入学业成绩"
                    min="0" max="100" step="0.0001" />
                  <div v-if="errors.academic_score" class="error-message">{{ errors.academic_score }}</div>
                </div>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">学术专长</label>
                  <input type="number" class="form-control" v-model="formData.academic_specialty_total"
                    placeholder="系统自动计算" min="0" max="12" step="0.01" disabled />
                  <div class="help-text">由系统根据申请记录自动计算，直接计入综合成绩</div>
                </div>
                <div class="form-group">
                  <label class="form-label">综合表现</label>
                  <input type="number" class="form-control" v-model="formData.comprehensive_performance_total"
                    placeholder="系统自动计算" min="0" max="8" step="0.01" disabled />
                  <div class="help-text">由系统根据申请记录自动计算，直接计入综合成绩</div>
                </div>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">考核总分</label>
                  <input type="number" class="form-control" v-model="formData.total_score" placeholder="系统自动计算" min="0"
                    max="100" step="0.01" disabled />
                  <div class="help-text">由系统根据申请记录自动计算</div>
                </div>
                <div class="form-group">
                  <label class="form-label">综合成绩</label>
                  <input type="number" class="form-control" v-model="formData.comprehensive_score" placeholder="系统自动计算"
                    min="0" max="100" step="0.01" disabled />
                  <div class="help-text">计算方式：学业成绩 * 学业成绩权重 / 100 + 学术专长总分 + 综合表现总分</div>
                </div>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">专业排名</label>
                  <input type="number" class="form-control" v-model="formData.major_ranking" placeholder="系统自动计算"
                    min="1" step="1" disabled />
                  <div class="help-text">由系统根据申请记录自动计算</div>
                </div>
                <div class="form-group">
                  <label class="form-label">排名人数</label>
                  <input type="number" class="form-control" v-model="formData.total_students" placeholder="系统自动计算"
                    min="1" step="1" disabled />
                  <div class="help-text">由系统根据申请记录自动计算</div>
                </div>
              </div>
              <div class="form-actions">
                <button type="button" class="btn btn-outline" @click="dialogVisible = false">取消</button>
                <button type="submit" class="btn btn-primary">更新</button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 学院成绩设置弹窗 -->
  <div v-if="scoreSettingsDialogVisible" class="modal-overlay" @click.self="scoreSettingsDialogVisible = false">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h3>学院成绩设置</h3>
        <button class="close-btn" @click="scoreSettingsDialogVisible = false">
          <font-awesome-icon :icon="['fas', 'times']" />
        </button>
      </div>
      <div class="modal-body">
        <div class="form-group">
          <label for="academic_score_weight">学业成绩比例(%)</label>
          <div class="input-group">
            <input type="number" class="form-control" id="academic_score_weight"
              v-model.number="facultyScoreSettings.academic_score_weight" min="0" max="100" />
          </div>
        </div>
        <div class="form-group">
          <label for="specialty_max_score">学术专长分数上限</label>
          <input type="number" class="form-control" id="specialty_max_score"
            v-model.number="facultyScoreSettings.specialty_max_score" min="0" max="100" />
        </div>
        <div class="form-group">
          <label for="performance_max_score">综合表现分数上限</label>
          <input type="number" class="form-control" id="performance_max_score"
            v-model.number="facultyScoreSettings.performance_max_score" min="0" max="100" />
        </div>
        <div class="form-actions">
          <button type="button" class="btn btn-outline" @click="scoreSettingsDialogVisible = false">取消</button>
          <button type="button" class="btn btn-primary" @click="saveFacultyScoreSettings">保存</button>
        </div>
      </div>
    </div>
  </div>

</template>

<script>
import api from '../../utils/api'
import { useApplicationsStore } from '../../stores/applications'
import { useToastStore } from '../../stores/toast'
import { useAuthStore } from '../../stores/auth'

export default {
  name: 'ScoreManagement',
  components: {
  },
  setup() {
    return {
      toastStore: useToastStore(),
      authStore: useAuthStore()
    }
  },
  data() {
    return {
      // 表格数据
      scores: [],
      total: 0,
      loading: false,
      // 分页
      currentPage: 1,
      pageSize: 10,
      // 筛选条件
      filters: {
        studentId: '',
        studentName: '',
        faculty: 'all',
        department: 'all',
        major: 'all'
      },
      // 下拉选项数据
      faculties: [],
      departments: [],
      majors: [],
      // 模态框
      dialogVisible: false,
      // 表单数据
      formData: {
        id: null,
        student_id: '',
        student_name: '',
        gender: '',
        facultyName: '',
        departmentName: '',
        majorName: '',
        cet4_score: null,
        cet6_score: null,
        gpa: null,
        academic_score: null,
        academic_specialty_total: null,
        comprehensive_performance_total: null,
        total_score: null,
        comprehensive_score: null,
        major_ranking: null,
        total_students: null
      },
      // 表单验证错误
      errors: {},
      // 学院成绩设置相关
      scoreSettingsDialogVisible: false,
      selectedFaculty: null,
      selectedFacultyForSettings: '',
      scoreSettings: [], // 存储所有学院的成绩设置
      scoreSettingsSearch: '', // 学院成绩设置搜索框
      facultyScoreSettings: {
        faculty_id: null,
        academic_score_weight: 80,
        specialty_max_score: 15,
        performance_max_score: 5
      }
    }
  },
  computed: {
    totalPages() {
      return Math.ceil(this.total / this.pageSize)
    },
    startIndex() {
      return (this.currentPage - 1) * this.pageSize
    },
    endIndex() {
      return Math.min(this.startIndex + this.pageSize, this.total)
    },
    filteredScores() {
      let filtered = this.scores.filter(student => {
        const idMatch = !this.filters.studentId || student.student_id.includes(this.filters.studentId)
        const nameMatch = !this.filters.studentName || student.student_name.includes(this.filters.studentName)
        
        // 学院筛选：如果选择了"全部学院"或没有选择，匹配所有；否则根据学院ID查找对应的名称进行匹配
        const facultyMatch = () => {
          if (this.filters.faculty === 'all' || !this.filters.faculty) return true
          const selectedFaculty = this.faculties.find(f => f.id === this.filters.faculty)
          return selectedFaculty ? student.faculty === selectedFaculty.name : true
        }
        
        // 系筛选：如果选择了"全部系"或没有选择，匹配所有；否则根据系ID查找对应的名称进行匹配
        const departmentMatch = () => {
          if (this.filters.department === 'all' || !this.filters.department) return true
          const selectedDepartment = this.departments.find(d => d.id === this.filters.department)
          return selectedDepartment ? student.department === selectedDepartment.name : true
        }
        
        // 专业筛选：如果选择了"全部专业"或没有选择，匹配所有；否则根据专业ID查找对应的名称进行匹配
        const majorMatch = () => {
          if (this.filters.major === 'all' || !this.filters.major) return true
          const selectedMajor = this.majors.find(m => m.id === this.filters.major)
          return selectedMajor ? student.major === selectedMajor.name : true
        }

        return idMatch && nameMatch && facultyMatch() && departmentMatch() && majorMatch()
      })

      return filtered
    },
    filteredScoreSettings() {
      if (!this.scoreSettingsSearch) {
        return this.scoreSettings
      }
      const searchTerm = this.scoreSettingsSearch.toLowerCase()
      return this.scoreSettings.filter(setting => {
        const facultyName = this.getFacultyName(setting.faculty_id).toLowerCase()
        return facultyName.includes(searchTerm)
      })
    },
    paginatedScores() {
      // 前端实现分页
      return this.filteredScores.slice(this.startIndex, this.endIndex)
    }
  },
  watch: {
    // 实时监听筛选条件变化，自动更新列表
    filters: {
      handler() {
        this.currentPage = 1
        // 这里不需要重新加载API，因为筛选是在前端进行的
      },
      deep: true
    }
  },
  mounted() {
    this.loadAllData()
  },
  methods: {
    // 统一加载所有数据
    async loadAllData() {
      this.loading = true
      try {
        await Promise.all([
          this.loadScoresFromAPI(),
          this.loadDropdownData()
        ])
      } catch (error) {
        console.error('加载数据失败:', error)
        this.toastStore.error('加载成绩数据失败')
        console.error('Error loading scores:', error)
      } finally {
        this.loading = false
      }
    },
    // 从API加载成绩数据
    async loadScoresFromAPI() {
      try {
        // 使用applicationsStore加载学生排名数据
        const applicationsStore = useApplicationsStore()
        const responseData = await applicationsStore.fetchStudentsRanking()

        // 获取学生列表并转换字段名称
        let students = responseData.students || []
        students = students.map(student => {
          return {
            // 基本信息
            id: student.id,
            student_id: student.student_id,
            student_name: student.student_name,
            gender: student.gender,
            faculty: student.faculty,
            department: student.department,
            major: student.major,
            cet4_score: student.cet4_score,
            cet6_score: student.cet6_score,
            gpa: student.gpa,
            academic_score: student.academic_score,

            // 从排名数据获取的字段
            academic_specialty_total: student.specialty_score || 0,
            comprehensive_performance_total: student.comprehensive_performance_total || 0,
            total_score: student.total_comprehensive_score || student.total_score,
            comprehensive_score: student.comprehensive_score || 0,
            major_ranking: student.major_ranking,
            total_students: student.major_total_students
          }
        })

        // 更新数据
        this.scores = students
        this.total = this.filteredScores.length
        this.currentPage = 1
        this.pageSize = 10
      } catch (error) {
        this.toastStore.error('加载成绩数据失败')
        console.error('Error loading scores:', error)
      }
    },

    // 加载学院数据
    async loadFaculties() {
      try {
        // 使用管理员版本的API获取学院列表
        const response = await api.getFacultiesAdmin()
        // 从response.faculties字段提取数组
        this.faculties = response.faculties || []
        
        // 将管理员所在的学院设置为默认选中值
        const adminFacultyId = this.authStore.user?.faculty_id || this.authStore.user?.facultyId
        if (adminFacultyId) {
          this.filters.faculty = adminFacultyId
          // 根据默认学院加载系
          await this.loadDepartments(adminFacultyId)
        } else {
          // 如果没有默认学院，加载所有系
          await this.loadDepartments()
        }
      } catch (error) {
        console.error('获取学院列表失败:', error)
        this.faculties = []
      }
    },

    // 加载系数据
    async loadDepartments(facultyId = '') {
      try {
        // 获取管理员所在学院ID（用于权限控制）
        const adminFacultyId = this.authStore.user?.faculty_id || this.authStore.user?.facultyId
        let response
        
        // 优先使用传入的学院ID（用户选择），但确保在管理员权限范围内
        if (facultyId && facultyId !== 'all') {
          // 根据选择的学院ID获取系
          response = await api.getDepartmentsAdmin(facultyId)
        } else if (adminFacultyId && adminFacultyId !== 'all') {
          // 如果用户没有选择学院，但管理员有学院权限，使用管理员学院ID
          response = await api.getDepartmentsAdmin(adminFacultyId)
        } else {
          // 获取所有系（仅当管理员没有学院ID时）
          response = await api.getDepartmentsAdmin()
        }
        
        // 设置系数据
        this.departments = response.departments || []
        
        // 重置专业选择和列表
        this.filters.major = 'all'
        
        // 如果有系被选中但不在新列表中，重置系选择
        if (this.filters.department !== 'all' && !this.departments.some(dept => dept.id === this.filters.department)) {
          this.filters.department = 'all'
        }
        
        // 根据当前选择的系加载专业
        if (this.filters.department !== 'all') {
          await this.loadMajors(this.filters.department)
        } else {
          // 加载当前学院下所有系的专业
          await this.loadMajors()
        }
      } catch (error) {
        console.error('获取系列表失败:', error)
        this.departments = []
        this.majors = []
      }
    },

    // 加载专业数据
    async loadMajors(departmentId = '') {
      try {
        // 获取管理员所在学院ID（用于权限控制）
        const adminFacultyId = this.authStore.user?.faculty_id || this.authStore.user?.facultyId
        let response
        
        // 如果指定了系ID，获取该系下的专业
        if (departmentId && departmentId !== 'all') {
          response = await api.getMajorsAdmin(departmentId)
        } else {
          // 获取所有专业（考虑管理员学院权限）
          if (this.filters.faculty && this.filters.faculty !== 'all') {
            // 如果选择了学院但没有选择系，获取该学院下的所有专业
            response = await api.getMajorsAdmin('', this.filters.faculty)
          } else if (adminFacultyId && adminFacultyId !== 'all') {
            // 如果没有选择学院，但管理员有学院权限，获取该学院下的所有专业
            response = await api.getMajorsAdmin('', adminFacultyId)
          } else {
            // 没有学院限制，获取所有专业
            response = await api.getMajorsAdmin()
          }
        }
        
        // 设置专业数据
        this.majors = response.majors || []
        
        // 如果有专业被选中但不在新列表中，重置专业选择
        if (this.filters.major !== 'all' && !this.majors.some(major => major.id === this.filters.major)) {
          this.filters.major = 'all'
        }
      } catch (error) {
        console.error('获取专业列表失败:', error)
        this.majors = []
      }
    },

    // 加载下拉选项数据
    async loadDropdownData() {
      try {
        // 先加载学院列表，确保学院数据可用
        await this.loadFaculties()
        // 再加载成绩设置
        await this.loadAllFacultyScoreSettings()
      } catch (error) {
        console.error('加载下拉数据失败:', error)
      }
    },

    // 加载所有学院的成绩设置
    async loadAllFacultyScoreSettings() {
      try {
        // 调用API获取所有学院的成绩设置
        const response = await api.getFacultyScoreSettings()
        let existingSettings = response.settings || []

        // 为所有学院创建成绩设置，已有设置的使用现有设置，没有的创建默认设置
        this.scoreSettings = this.faculties.map(faculty => {
          // 查找现有设置
          const existingSetting = existingSettings.find(setting => setting.faculty_id === faculty.id)
          if (existingSetting) {
            // 使用现有设置
            return existingSetting
          } else {
            // 创建默认设置
            return {
              faculty_id: faculty.id,
              academic_score_weight: 80,
              specialty_max_score: 15,
              performance_max_score: 5
            }
          }
        })
      } catch (error) {
        console.error('加载所有学院成绩设置失败:', error)
        // 如果API调用失败，为所有学院创建默认设置
        if (this.faculties.length > 0) {
          this.scoreSettings = this.faculties.map(faculty => ({
            faculty_id: faculty.id,
            academic_score_weight: 80,
            specialty_max_score: 15,
            performance_max_score: 5
          }))
        } else {
          // 如果学院列表为空，初始化空数组
          this.scoreSettings = []
        }
      }
    },

    // 学院选择变化时的处理
    async onFacultyChange() {
      this.filters.department = 'all'
      this.filters.major = 'all'

      // 根据选择的学院加载系
      if (this.filters.faculty && this.filters.faculty !== 'all') {
        await this.loadDepartments(this.filters.faculty)
      } else {
        await this.loadDepartments()
      }

      this.currentPage = 1
    },

    // 系选择变化时的处理
    async onDepartmentChange() {
      this.filters.major = 'all'

      // 根据选择的系加载专业
      if (this.filters.department && this.filters.department !== 'all') {
        await this.loadMajors(this.filters.department)
      } else {
        await this.loadMajors()
      }

      this.currentPage = 1
    },

    // 重置筛选条件
    async resetFilter() {
      // 保存当前学院选择
      const currentFaculty = this.filters.faculty
      
      Object.assign(this.filters, {
        studentId: '',
        studentName: '',
        faculty: currentFaculty, // 保持当前学院选择不变
        department: 'all',
        major: 'all'
      })
      
      // 重置后重新加载数据
      await this.loadDepartments(currentFaculty)
      this.currentPage = 1
    },

    // 分页相关
    prevPage() {
      if (this.currentPage > 1) {
        this.currentPage--
      }
    },

    nextPage() {
      if (this.currentPage < this.totalPages) {
        this.currentPage++
      }
    },

    // 打开编辑模态框
    openEditModal(row) {
      this.formData = {
        id: row.id, // 使用主键ID作为更新API的ID参数
        student_id: row.student_id,
        student_name: row.student_name,
        gender: row.gender,
        facultyName: row.faculty,
        departmentName: row.department,
        majorName: row.major,
        cet4_score: row.cet4_score,
        cet6_score: row.cet6_score,
        gpa: row.gpa,
        academic_score: row.academic_score,
        academic_specialty_total: row.academic_specialty_total,
        comprehensive_performance_total: row.comprehensive_performance_total,
        total_score: row.total_score,
        comprehensive_score: row.comprehensive_score,
        major_ranking: row.major_ranking,
        total_students: row.total_students
      }
      this.errors = {}
      this.dialogVisible = true
    },

    // 表单验证
    validateForm() {
      this.errors = {}
      let isValid = true

      if (!this.formData.gender) {
        this.errors.gender = '请选择性别'
        isValid = false
      }

      return isValid
    },

    // 提交表单
    async handleSubmit() {
      if (this.validateForm()) {
        try {
          // 更新学生
          await api.updateStudentAdmin(this.formData.id, this.formData)

          // 关闭模态框并刷新数据
          this.dialogVisible = false
          this.loadScoresFromAPI()
          this.toastStore.success('成绩信息更新成功')
        } catch (error) {
          this.toastStore.error('更新成绩信息失败')
          console.error('Error submitting student form:', error)
        }
      }
    },

    // 重新计算所有学生的综合成绩
    async recalculateComprehensiveScores() {
      try {
        // 显示确认对话框
        if (confirm('确定要重新计算所有学生的综合成绩吗？此操作可能需要一些时间。')) {
          this.loading = true

          // 获取当前登录用户信息
          const userInfo = JSON.parse(localStorage.getItem('user'))

          // 调用API重新计算综合成绩
          await api.recalculateComprehensiveScores({ username: userInfo?.username })

          // 刷新成绩数据
          await this.loadScoresFromAPI()

          this.toastStore.success('综合成绩重新计算完成')
        }
      } catch (error) {
        console.error('Error recalculating comprehensive scores:', error)
        this.toastStore.error('重新计算综合成绩失败')
      } finally {
        this.loading = false
      }
    },

    // 打开成绩设置对话框
    openScoreSettingsDialog(setting = null) {
      if (setting) {
        // 编辑已有设置
        this.facultyScoreSettings = { ...setting };
        this.selectedFaculty = this.faculties.find(f => f.id === setting.faculty_id);
      } else {
        // 创建新设置（默认使用第一个学院）
        if (this.faculties.length > 0) {
          this.selectedFaculty = this.faculties[0];
          this.facultyScoreSettings = {
            faculty_id: this.selectedFaculty.id,
            academic_score_weight: 80,
            specialty_max_score: 15,
            performance_max_score: 5
          };
        } else {
          // 如果学院列表为空，初始化默认设置
          this.facultyScoreSettings = {
            faculty_id: null,
            academic_score_weight: 80,
            specialty_max_score: 15,
            performance_max_score: 5
          };
          this.selectedFaculty = null;
        }
      }
      this.scoreSettingsDialogVisible = true;
    },

    // 根据学院ID获取学院名称
    getFacultyName(facultyId) {
      const faculty = this.faculties.find(f => f.id === facultyId);
      return faculty ? faculty.name : '未知学院';
    },

    // 加载学院成绩设置
    async loadFacultyScoreSettings(facultyId) {
      try {
        this.loading = true
        const settings = await api.getFacultyScoreSetting(facultyId)
        if (settings) {
          this.facultyScoreSettings = settings
        } else {
          // 如果没有找到设置，使用默认值
          this.facultyScoreSettings = {
            faculty_id: facultyId,
            final_exam_weight: 0.5,
            usual_score_weight: 0.3,
            practice_score_weight: 0.2
          }
        }
      } catch (error) {
        console.error('Error loading faculty score settings:', error)
        this.toastStore.error('加载学院成绩设置失败')
        // 使用默认值
        this.facultyScoreSettings = {
          faculty_id: facultyId,
          final_exam_weight: 0.5,
          usual_score_weight: 0.3,
          practice_score_weight: 0.2
        }
      } finally {
        this.loading = false
      }
    },

    // 保存学院成绩设置
    async saveFacultyScoreSettings() {
      try {
        // 调用API保存学院成绩设置
        await api.updateFacultyScoreSetting(this.facultyScoreSettings.faculty_id, this.facultyScoreSettings)

        // 更新本地的scoreSettings数组
        const index = this.scoreSettings.findIndex(s => s.faculty_id === this.facultyScoreSettings.faculty_id)
        if (index !== -1) {
          this.scoreSettings[index] = { ...this.facultyScoreSettings }
        } else {
          this.scoreSettings.push({ ...this.facultyScoreSettings })
        }

        // 关闭对话框
        this.scoreSettingsDialogVisible = false

        // 显示成功消息
        this.toastStore.success('学院成绩设置保存成功')
      } catch (error) {
        console.error('Error saving faculty score settings:', error)
        this.toastStore.error('学院成绩设置保存失败')
      }
    }
  }
}
</script>

<style scoped>
/* 引入共享样式 */
@import '../common/shared-styles.css';
</style>