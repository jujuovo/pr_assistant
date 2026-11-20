"""信息学院 2025 年2月修订办法，第7–8页，自2028届实施。"""
from decimal import Decimal, ROUND_FLOOR
from services.volunteer_rules import parse_number

POLICY_ID = 'xmu-informatics-2025-02-volunteer-hours-v1'
SOURCE_SHA256 = '48a8e4de880b6239aa0090c5b76e2358a3e577731cc2d98fd19e6c28e5dc43c4'


def calculate_hours(regular_hours, reduced_hours):
    regular, reduced = parse_number(regular_hours), parse_number(reduced_hours)
    effective = regular + reduced / 2
    steps = (max(effective - 200, Decimal(0)) / 2).to_integral_value(rounding=ROUND_FLOOR)
    score = min(steps * Decimal('0.05'), Decimal(1))
    return {'policy_id': POLICY_ID, 'source_sha256': SOURCE_SHA256,
            'regular_hours': str(regular), 'reduced_hours': str(reduced),
            'effective_hours': str(effective), 'score': str(score.quantize(Decimal('0.0001'))),
            'formula': 'min(1, floor(max(普通工时 + 大型赛会及支教工时 / 2 - 200, 0) / 2) × 0.05)'}
