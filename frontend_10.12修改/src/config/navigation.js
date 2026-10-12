// 页面标识与角色布局内的 pageComponents 对应，顺序决定侧栏显示顺序。
export const roleNavigation = {
  teacher: [
    { key: 'pending-review', icon: ['fas', 'file-upload'], title: '待审核申请' },
    { key: 'review-history', icon: ['fas', 'history'], title: '审核记录' },
    { key: 'statistics-report', icon: ['fas', 'chart-pie'], title: '统计报表' },
    { key: 'profile', icon: ['fas', 'user'], title: '个人信息' }
  ],
  admin: [
    { key: 'user-management', icon: ['fas', 'users'], title: '用户管理' },
    { key: 'faculty-management', icon: ['fas', 'university'], title: '学院管理' },
    { key: 'data-management', icon: ['fas', 'database'], title: '申请管理' },
    { key: 'score-management', icon: ['fas', 'user-graduate'], title: '成绩管理' },
    { key: 'rule-management', icon: ['fas', 'ruler'], title: '规则管理' },
    { key: 'statistics-report', icon: ['fas', 'chart-pie'], title: '统计报表' },
    { key: 'graduate-file-management', icon: ['fas', 'file-lines'], title: '推免文件管理' },
    { key: 'system-settings', icon: ['fas', 'cog'], title: '系统设置' },
    { key: 'profile', icon: ['fas', 'user'], title: '个人信息' }
  ]
}
