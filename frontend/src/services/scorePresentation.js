const comprehensiveCategories = new Set([
  'comprehensive', 'international_internship', 'military_service', 'volunteer',
  'social_work', 'sports', 'honor_title'
])

export function scoreRows(dto) {
  return (dto?.entries || []).map(entry => {
    const source = entry.project_source || {}
    const category = source.category || 'unknown'
    return {
      id: entry.id ?? `${source.type}:${source.id}`,
      title: `${category} · ${source.type || 'source'} #${source.id || '-'}`,
      group: comprehensiveCategories.has(category) ? 'comprehensive' : 'academic',
      verificationStatus: entry.verification_status,
      scoringStatus: entry.scoring_status,
      ruleVersionId: entry.rule_version_id,
      sourceVersion: entry.source_version,
      sourceType: source.type,
      sourceId: source.id,
      category,
      candidateScore: entry.candidate_score ?? entry.automatic_score,
      includedScore: entry.included_score,
      included: entry.included,
      reason: entry.exclusion_reason,
      updatedAt: entry.updated_at,
      allowedActions: entry.allowed_actions || []
    }
  })
}
