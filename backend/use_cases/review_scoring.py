"""Shared command and result contract for evidence review plus scoring."""

from dataclasses import asdict, dataclass
from decimal import Decimal
import hashlib
import json


class ReviewScoringError(ValueError):
    def __init__(self, message, *, code="invalid_review_command", status_code=400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


ERROR_CODES = frozenset({
    "invalid_review_command",
    "forbidden",
    "source_not_found",
    "version_conflict",
    "idempotency_conflict",
    "cycle_policy_missing",
    "award_date_missing",
    "needs_rule",
    "ambiguous_rules",
    "override_reason_required",
    "override_out_of_range",
    "snapshot_failed",
})


@dataclass(frozen=True)
class ReviewScoringInput:
    source_type: str
    source_id: str
    source_version: int
    decision: str
    comment: str
    idempotency_key: str
    override_score: str | None = None
    override_reason: str | None = None

    def __post_init__(self):
        if not self.source_type or len(self.source_type) > 32:
            raise ReviewScoringError("source_type 无效")
        if not self.source_id or len(self.source_id) > 128:
            raise ReviewScoringError("source_id 无效")
        if type(self.source_version) is not int or self.source_version < 1:
            raise ReviewScoringError("source_version 必须为正整数")
        if self.decision not in {"verified", "rejected", "needs_correction"}:
            raise ReviewScoringError("decision 无效")
        if not isinstance(self.comment, str) or len(self.comment) > 2000:
            raise ReviewScoringError("comment 必须为不超过2000字符的文字")
        if not self.idempotency_key or len(self.idempotency_key) > 128:
            raise ReviewScoringError("idempotency_key 无效")
        if self.override_score is not None:
            try:
                score = Decimal(self.override_score)
            except Exception as error:
                raise ReviewScoringError("override_score 无效") from error
            if not score.is_finite() or score < 0:
                raise ReviewScoringError("override_score 无效")

    def digest(self, actor_id):
        payload = asdict(self) | {"actor_id": actor_id}
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def review_scoring_result(
    *, overall_status, verification_status, scoring_status, allowed_actions,
    cycle=None, eligibility=None, scoring=None, snapshot=None,
):
    if overall_status not in {"complete", "blocked", "failed"}:
        raise ValueError("invalid overall_status")
    if not isinstance(allowed_actions, list) or any(
        not isinstance(item, str) for item in allowed_actions
    ):
        raise ValueError("allowed_actions must be a list of strings")
    return {
        "overall_status": overall_status,
        "verification_status": verification_status,
        "scoring_status": scoring_status,
        "cycle": cycle,
        "eligibility": eligibility,
        "scoring": scoring,
        "snapshot": snapshot,
        "allowed_actions": allowed_actions,
    }
