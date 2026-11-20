"""Pure category adapters for the shared MaterialRecord -> ScoreEntry flow."""
from domain.scoring import ScoreRuleError, calculate_score
from domain.volunteer_policy import POLICY_ID, SOURCE_SHA256, calculate_hours


def calculate_material_score(category, facts, rule_snapshot):
    """Compute from fixed policy; transaction and ledger writes belong to callers."""
    if category == 'volunteer':
        if rule_snapshot.get('calculation_formula') != {
                'policy_id': POLICY_ID, 'source_sha256': SOURCE_SHA256}:
            raise ScoreRuleError('志愿工时必须使用学院2025年2月修订办法')
        result = calculate_hours(facts['regular_hours'], facts['reduced_hours'])
        return calculate_score({'score': result['score'], 'max_score': 1})
    return calculate_score(rule_snapshot)
