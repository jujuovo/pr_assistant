// 页面标识与角色布局内的 pageComponents 对应，顺序决定侧栏显示顺序。
export const roleNavigation = {
  teacher: [
    { key: 'profile', icon: 'user', title: '个人信息' },
    {
      id: 'recommendation-review',
      icon: 'file-circle-check',
      title: '推免审核',
      items: [
        { key: 'pending-review', icon: 'file-arrow-up', title: '待审核申请' },
        { key: 'review-history', icon: 'clock-rotate-left', title: '审核记录' },
        { key: 'statistics-report', icon: 'chart-pie', title: '统计报表' }
      ]
    }
  ],
  admin: [
    { key: 'profile', icon: 'user', title: '个人信息' },
    {
      id: 'recommendation-management',
      icon: 'folder-open',
      title: '推免管理',
      items: [
        { key: 'rule-management', icon: 'scale-balanced', title: '推免规则' },
        { key: 'graduate-file-management', icon: 'file-lines', title: '推免文件' }
      ]
    },
    {
      id: 'recommendation-statistics',
      icon: 'chart-column',
      title: '推免统计',
      items: [
        { key: 'statistics-report', icon: 'chart-pie', title: '统计报表' },
        { key: 'score-management', icon: 'user-graduate', title: '成绩管理' },
        { key: 'data-management', icon: 'database', title: '申请管理' }
      ]
    },
    {
      id: 'system-management',
      icon: 'gears',
      title: '系统管理',
      items: [
        { key: 'user-management', icon: 'users', title: '用户管理' },
        { key: 'faculty-management', icon: 'building-columns', title: '学院管理' },
        { key: 'system-settings', icon: 'gear', title: '系统设置' }
      ]
    }
  ]
}
