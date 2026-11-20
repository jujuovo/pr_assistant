// One destination for every visible submission category. Existing legacy records
// remain editable in their original form; new material categories share one hub.
export const materialCategoryRoutes = Object.freeze({
  competition: 'competition',
  'social-practice': 'social_practice',
  'academic-paper': 'research_paper',
  'innovation-training': 'innovation_training',
  'social-work': 'student_work'
  ,'volunteer-service': 'volunteer'
})

export function submissionQuery(key) {
  if (key === 'academic-innovation') return { page: 'application-categories' }
  const category = materialCategoryRoutes[key]
  if (category) return { page: 'materials', category }
  if (key === 'academic-performance') return { page: 'academic-performance' }
  return { page: 'application-form', categoryKey: key }
}
