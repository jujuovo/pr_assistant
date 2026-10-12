// Only loaded by `vite --mode demo`. All demo requests stay inside this browser.
const key = 'gradpush-home-demo-v1'
const organization = {
  faculty: '信息学院',
  department: '计算机科学与技术系',
  major: '软件工程',
  facultyId: 1,
  departmentId: 1,
  majorId: 1,
  faculty_id: 1,
  department_id: 1,
  major_id: 1
}
const users = ['student', 'teacher', 'admin'].map((role, i) => ({
  ...organization,
  id: i + 1,
  username: `${role}001`,
  name: ['演示同学', '演示教师', '演示管理员'][i],
  role,
  studentId: 'student001',
  student_id: 'student001',
  gender: '女',
  email: 'demo@example.com',
  phone: '13800000000',
  status: 'active',
  ...(role === 'admin' ? { facultyId: null, faculty_id: null } : {})
}))
const calculation = {
  id: 1,
  calculation_type: 'tree',
  max_score: 10,
  parameters: {
    type: 'tree',
    tree: {
      root: {
        id: 'root',
        dimension: { name: '获奖等级', key: 'level' },
        children: [
          { id: 'first', dimension: { name: '一等奖', key: 'first' }, score: 5, children: [] },
          { id: 'second', dimension: { name: '二等奖', key: 'second' }, score: 3, children: [] }
        ]
      }
    }
  }
}
const seed = () => ({
  users,
  faculties: [{ id: 1, name: '信息学院', code: 'INFO', description: '演示学院' }],
  departments: [
    {
      id: 1,
      name: '计算机科学与技术系',
      code: 'CS',
      faculty_id: 1,
      facultyId: 1,
      faculty_name: '信息学院'
    }
  ],
  majors: [
    {
      id: 1,
      name: '软件工程',
      code: 'SE',
      department_id: 1,
      departmentId: 1,
      faculty_id: 1,
      department_name: '计算机科学与技术系',
      faculty_name: '信息学院'
    }
  ],
  rules: [
    {
      id: 1,
      name: '学科竞赛加分（演示）',
      type: 'academic',
      sub_type: 'competition',
      status: 'active',
      faculty_id: 1,
      faculty_name: '信息学院',
      max_score: 10,
      max_count: 5,
      score: 5,
      description: '演示规则：一等奖 5 分，二等奖 3 分。',
      calculation,
      calculation_formula: calculation.parameters
    }
  ],
  applications: ['pending', 'approved', 'rejected', 'draft'].map((status, i) => ({
    ...organization,
    id: i + 1,
    studentId: 'student001',
    studentName: '演示同学',
    name: '演示同学',
    applicationType: 'academic',
    ruleId: 1,
    ruleName: '学科竞赛加分（演示）',
    projectName: ['程序设计竞赛', '数学建模竞赛', '创新项目', '待完善的申请'][i],
    awardDate: '2026-09-01',
    appliedAt: '2026-09-20T10:00:00',
    createdAt: '2026-09-20T10:00:00',
    status,
    selfScore: 5,
    finalScore: status === 'approved' ? 5 : 0,
    reviewComment: status === 'rejected' ? '请补充证明材料（演示）' : '材料完整（演示）',
    reviewedBy: 'teacher001',
    reviewedAt: status === 'approved' ? '2026-09-21T10:00:00' : null,
    description: '用于预览申请详情的示例数据。',
    files: [],
    dynamicCoefficients: {},
    tree_path: ['一等奖']
  })),
  settings: {
    academicYear: '2026',
    applicationStart: '2026-09-01T00:00',
    applicationEnd: '2026-10-31T23:59',
    applicationStartTime: '2026-09-01T00:00',
    applicationEndTime: '2026-10-31T23:59',
    singleFileSizeLimit: 10,
    totalFileSizeLimit: 50,
    avatarFileSizeLimit: 5,
    allowedFileTypes: '.pdf,.jpg,.jpeg,.png,.docx',
    systemStatus: '正常运行'
  },
  scoreSettings: [
    { faculty_id: 1, academic_score_weight: 80, specialty_max_score: 15, performance_max_score: 5 }
  ],
  files: [
    {
      id: 1,
      filename: '推免申请说明（演示）.html',
      file_url: '/demo-guide.html',
      file_size: 600,
      upload_time: '2026-09-29T10:00:00',
      faculty: { id: 1, name: '信息学院' }
    }
  ],
  backups: [],
  logs: [{ name: 'demo.log', size: 64, create_time: '2026-09-29T10:00:00' }]
})
let db
try {
  db = JSON.parse(localStorage.getItem(key))
} catch {}
db ||= seed()
const save = () => localStorage.setItem(key, JSON.stringify(db))
const success = (extra = {}) => ({
  success: true,
  message: '演示操作完成，仅保存到当前浏览器',
  ...extra
})
const current = () =>
  db.users.find((u) => u.username === sessionStorage.getItem('gradpush-demo-user')) || db.users[0]
const camel = (data) =>
  Object.fromEntries(
    Object.entries(data).map(([k, v]) => [k.replace(/_([a-z])/g, (_, c) => c.toUpperCase()), v])
  )
const stats = () => ({
  ...organization,
  ...db.users[0],
  student_name: db.users[0].name,
  gpa: db.users[0].gpa || 3.8,
  academic_score: db.users[0].academic_score || 76,
  specialty_score: 5,
  comprehensive_performance_total: 3,
  total_score: 84,
  total_comprehensive_score: 84,
  comprehensive_score: 84,
  ranking: 1,
  major_ranking: 1,
  major_total_students: 30,
  cet4_score: 580,
  cet6_score: 550,
  academic_items: [],
  comprehensive_items: []
})
function route(path, method, data, query) {
  if (path === '/login') {
    const user = db.users.find((u) => u.username === String(data.username || '').trim())
    const validCredentials =
      data.password === 'demo123' && data.captcha === '1234' && data.captchaToken === 'demo'
    if (!user || !validCredentials) throw new Error('账号、密码或验证码错误')
    sessionStorage.setItem('gradpush-demo-user', user.username)
    return { user }
  }
  if (path === '/logout') {
    sessionStorage.removeItem('gradpush-demo-user')
    return success()
  }
  if (path === '/session-check')
    return { logged_in: !!sessionStorage.getItem('gradpush-demo-user') }
  if (path === '/generate-captcha') {
    const canvas = document.createElement('canvas')
    canvas.width = 100
    canvas.height = 40
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#eef2ff'
    ctx.fillRect(0, 0, 100, 40)
    ctx.fillStyle = '#334155'
    ctx.font = '24px sans-serif'
    ctx.fillText('1234', 18, 28)
    return { image: canvas.toDataURL().split(',')[1], token: 'demo' }
  }
  if (path === '/register' || path === '/reset-password' || path.endsWith('/change-password'))
    return success()
  if (path.startsWith('/user/')) {
    if (path === '/user/avatar') data = { avatar: URL.createObjectURL(data.avatar) }
    if (path === '/user/avatar/reset') data = { avatar: '' }
    if (method !== 'GET') Object.assign(current(), data)
    return success({ user: current() })
  }
  if (path === '/public/system-info') return { data: db.settings }
  if (path === '/admin/system-settings') {
    if (method !== 'GET') Object.assign(db.settings, data)
    return { settings: db.settings }
  }
  if (path.startsWith('/admin/faculty-score-settings')) {
    const id = Number(path.split('/')[3])
    if (method !== 'GET') Object.assign(db.scoreSettings[0], data)
    return {
      settings: id
        ? db.scoreSettings.find((s) => s.faculty_id === id) || db.scoreSettings[0]
        : db.scoreSettings
    }
  }
  if (path === '/students/statistics') return stats()
  if (path === '/students/ranking' || path === '/students') return { students: [stats()], total: 1 }
  if (path.startsWith('/students/')) {
    Object.assign(db.users[0], data)
    return success()
  }
  if (path.includes('/graduate-files')) {
    if (method === 'POST') {
      const file = data.file
      db.files.push({
        id: Date.now(),
        filename: file?.name || '演示文件',
        original_filename: file?.name,
        file_name: file?.name,
        file_url: file instanceof Blob ? URL.createObjectURL(file) : '',
        file_size: file?.size || 0,
        upload_time: new Date().toISOString(),
        faculty_id: Number(data.faculty_id) || 1,
        description: data.description || ''
      })
    }
    if (method === 'DELETE')
      db.files = db.files.filter((f) => f.id !== Number(path.split('/').pop()))
    return success({ files: db.files })
  }
  if (path === '/rules/match') return { rules: db.rules, data: db.rules }
  if (/\/rules\/\d+\/calculate$/.test(path)) return success({ data: { score: 5 } })
  if (/\/rules\/\d+\/calculation$/.test(path))
    return success({
      data: db.rules.find((r) => r.id === Number(path.split('/')[2]))?.calculation || calculation
    })
  if (path.startsWith('/calculations/')) return success({ data })
  if (path.startsWith('/system/')) {
    if (path === '/system/backup' && method === 'POST')
      db.backups.push({
        name: `demo-${Date.now()}.json`,
        size: 64,
        create_time: new Date().toISOString(),
        download_url: '/api/system/backup/download/demo.json'
      })
    if (path.includes('/backup/delete/'))
      db.backups = db.backups.filter((b) => b.name !== path.split('/').pop())
    return success({
      backups: db.backups,
      logs: db.logs,
      content: '[DEMO] 前端演示运行正常；未连接服务器。'
    })
  }
  if (path.includes('import-'))
    return {
      success: false,
      message: '演示模式不执行批量导入；可使用新增按钮体验表单。',
      errors: ['未连接后端，未导入真实数据。']
    }
  const match = path.match(
    /^\/(?:admin\/)?(faculties|departments|majors|rules|applications|users|create-users)(?:\/([^/]+))?(?:\/(.+))?$/
  )
  if (match) {
    const collection = match[1] === 'create-users' ? 'users' : match[1]
    const id = Number(match[2])
    const list = db[collection]
    const item = list.find((x) => x.id === id)
    if (method === 'DELETE') db[collection] = list.filter((x) => x.id !== id)
    else if (method !== 'GET') {
      if (match[2] === 'batch-delete')
        db[collection] = list.filter((x) => !data.ids?.includes(x.id))
      else if (item) {
        Object.assign(item, data)
        if (match[3] === 'status') item.status = item.status === 'active' ? 'inactive' : 'active'
        if (match[3] === 'review') item.reviewedAt = new Date().toISOString()
      } else {
        const created = {
          ...data,
          id: Date.now(),
          createdAt: new Date().toISOString(),
          appliedAt: new Date().toISOString()
        }
        list.push(created)
        return success({ ...created, data: created, user: created })
      }
    }
    if (collection === 'applications') {
      let rows = db.applications
      if (match[2] === 'pending') rows = rows.filter((x) => x.status === 'pending')
      for (const field of ['status', 'studentId', 'applicationType']) {
        const v = query.get(field)
        if (v && v !== 'all') rows = rows.filter((x) => String(x[field]) === v)
      }
      return id ? item || {} : rows
    }
    if (collection === 'rules' && id) return success({ data: item, ...item })
    if (collection === 'users') {
      const rows = db.users.filter(
        (u) => !query.get('role') || query.get('role') === 'all' || u.role === query.get('role')
      )
      return success({ users: rows, total: rows.length, pages: 1 })
    }
    return success({ [collection]: db[collection], data: item })
  }
  throw new Error(`尚未实现的演示操作：${method} ${path}`)
}
export function installDemo() {
  const originalFetch = window.fetch.bind(window)
  window.fetch = async (input, options = {}) => {
    const url = new URL(typeof input === 'string' ? input : input.url, location.origin)
    if (url.origin !== location.origin || !url.pathname.startsWith('/api/'))
      return originalFetch(input, options)
    let data =
      options.body instanceof FormData
        ? Object.fromEntries(options.body.entries())
        : typeof options.body === 'string'
          ? JSON.parse(options.body)
          : {}
    if (data.application) data = { ...camel(JSON.parse(data.application)), files: [] }
    try {
      const result = route(url.pathname.slice(4), options.method || 'GET', data, url.searchParams)
      save()
      return Response.json(result)
    } catch (error) {
      console.error(error)
      return Response.json({ message: error.message }, { status: 400 })
    }
  }
}
export function resetDemo() {
  localStorage.removeItem(key)
  sessionStorage.removeItem('gradpush-demo-user')
  localStorage.removeItem('gradpush-demo-auth')
  location.href = '/login'
}
