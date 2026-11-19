// Shared display order and OCR fallback for preview and teacher review.
export const CERTIFICATE_FIELDS = Object.freeze({
  school: '学校', student: '姓名', teacher: '指导教师', edition: '届次',
  track: '赛道', group: '组别', region: '赛区', award: '奖项',
  certificate_no: '证书编号', date: '日期'
})

export const recognizedCertificateValue = (page, field) =>
  page.processed_fields?.[field] || page.raw_fields?.[field] || ''
