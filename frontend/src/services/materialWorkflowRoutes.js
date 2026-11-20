// One destination for every visible submission category. Existing legacy records
// remain editable in their original form; new material categories share one hub.
export const materialCategoryRoutes = Object.freeze({
  competition: 'competition',
  'social-practice': 'social_practice',
  'academic-innovation': 'research',
  'social-work': 'student_work',
  'volunteer-service': 'volunteer',
  'arts-sports': 'arts_sports'
})

export function submissionQuery(key) {
  const category = materialCategoryRoutes[key]
  if (category) return { page: 'materials', category }
  if (key === 'academic-performance') return { page: 'academic-performance' }
  return { page: 'application-form', categoryKey: key }
}
