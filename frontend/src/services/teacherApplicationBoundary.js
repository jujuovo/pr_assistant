// Legacy Application review remains available only for noncompetition categories.
export function isNonCompetitionCompatibilityApplication(application) {
  const category = application?.rule?.sub_type ?? application?.rule?.subType ??
    application?.sub_type ?? application?.subType ?? application?.category
  return category !== 'competition'
}

export function nonCompetitionRules(rules = []) {
  return rules.filter(rule => (rule.sub_type ?? rule.subType) !== 'competition')
}
