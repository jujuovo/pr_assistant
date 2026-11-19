const DERIVED = new Set([
  'academic_specialty_total','specialty_score','comprehensive_performance_total',
  'performance_score','total_score','comprehensive_score','major_ranking','total_students'
])

export function buildStudentBaseUpdate(form) {
  return Object.fromEntries(Object.entries(form || {}).filter(([key]) =>
    key !== 'id' && !DERIVED.has(key) && !key.endsWith('Name') && key !== 'student_id'))
}

export function scoreAuthorityMeta(row) {
  return {
    version: row.snapshot_version ?? null,
    status: row.snapshot_status || 'no_authoritative_snapshot',
    updatedAt: row.snapshot_updated_at || null
  }
}
