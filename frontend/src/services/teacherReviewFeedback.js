export function teacherReviewError(error) {
  const messages = {
    review_not_available: '该材料尚未由学生正式提交，无需教师处理',
    source_version_conflict: '材料版本已变化，请刷新后重试',
    needs_correction: '材料需要学生补正后重新提交'
  }
  return messages[error?.code] || '审核失败，请稍后重试'
}
