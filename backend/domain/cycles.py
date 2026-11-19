"""Pure recommendation-cycle and evidence-date policies."""

from dataclasses import dataclass
from datetime import date


class CyclePolicyError(ValueError):
    pass


@dataclass(frozen=True)
class DateEligibility:
    status: str
    reason: str | None

    @property
    def eligible(self):
        return self.status == "eligible"


def normalize_cycle_code(value):
    if isinstance(value, bool):
        raise CyclePolicyError("cycle code must be a four-digit year")
    try:
        code = int(value)
    except (TypeError, ValueError):
        raise CyclePolicyError("cycle code must be a four-digit year") from None
    if not 2000 <= code <= 2100 or str(code) != str(value).strip():
        raise CyclePolicyError("cycle code must be a four-digit year")
    return code


def evaluate_award_date(award_date, start_date, end_date):
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise CyclePolicyError("cycle award window requires date boundaries")
    if end_date < start_date:
        raise CyclePolicyError("cycle award window end precedes start")
    if award_date is None:
        return DateEligibility("needs_correction", "missing_award_date")
    if not isinstance(award_date, date):
        return DateEligibility("needs_correction", "invalid_award_date")
    if start_date <= award_date <= end_date:
        return DateEligibility("eligible", None)
    return DateEligibility("not_eligible", "award_date_outside_cycle_window")
