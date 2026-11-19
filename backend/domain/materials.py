"""Material evidence state and authorization policies.

This module is deliberately transport- and persistence-agnostic.  HTTP
adapters translate :class:`MaterialPolicyError` into their own response type.
"""

from dataclasses import dataclass


MATERIAL_STATUSES = frozenset(
    {
        "draft", "rule_unmatched", "rule_available", "submitted",
        "under_review", "needs_correction", "verified_not_eligible", "scored",
        # Legacy projections remain readable during the gradual migration.
        "verified", "rejected",
        "abandoned",
        "rule_reconfirmation_required",
    }
)

TRANSITIONS = frozenset({
    ("edit", "draft", "draft"),
    ("edit", "rule_unmatched", "draft"),
    ("edit", "rule_available", "draft"),
    ("edit", "needs_correction", "draft"),
    ("add_attachment", "draft", "draft"),
    ("add_attachment", "rule_unmatched", "draft"),
    ("add_attachment", "rule_available", "draft"),
    ("add_attachment", "needs_correction", "draft"),
    ("save_unmatched", "draft", "rule_unmatched"),
    ("mark_rule_available", "rule_unmatched", "rule_available"),
    ("submit", "draft", "submitted"),
    ("abandon", "draft", "abandoned"),
    ("confirm_submit", "rule_available", "submitted"),
    ("withdraw", "submitted", "draft"),
    ("abandon", "needs_correction", "abandoned"),
    ("begin_review", "submitted", "under_review"),
    ("review", "submitted", "verified"),
    ("review", "submitted", "rejected"),
    ("review", "submitted", "needs_correction"),
    ("review", "submitted", "verified_not_eligible"),
    ("review", "submitted", "scored"),
    ("review", "under_review", "needs_correction"),
    ("review", "under_review", "verified_not_eligible"),
    ("review", "under_review", "scored"),
})


class MaterialPolicyError(ValueError):
    """Raised when an actor cannot perform a material transition."""


@dataclass(frozen=True)
class ActorScope:
    role: str
    student_id: str | None
    faculty_id: int | None


@dataclass(frozen=True)
class MaterialScope:
    student_id: str
    faculty_id: int
    status: str


def is_owner(actor: ActorScope, material: MaterialScope) -> bool:
    return actor.role == "student" and actor.student_id == material.student_id


def is_staff(actor: ActorScope, material: MaterialScope) -> bool:
    return (
        actor.role in {"teacher", "admin"}
        and actor.faculty_id is not None
        and actor.faculty_id == material.faculty_id
    )


def can_view(actor: ActorScope, material: MaterialScope) -> bool:
    return is_owner(actor, material) or is_staff(actor, material)


def allowed_actions(actor: ActorScope, material: MaterialScope) -> tuple[str, ...]:
    """Return stable action identifiers for the current actor and state."""
    if material.status not in MATERIAL_STATUSES or not can_view(actor, material):
        return ()
    actions = ["view", "download_attachment"]
    if is_owner(actor, material):
        if material.status in {"draft", "rule_unmatched", "rule_available", "needs_correction"}:
            actions.extend(("edit", "add_attachment"))
        if material.status == "draft":
            actions.extend(("submit", "save_unmatched", "abandon"))
        elif material.status == "rule_available":
            actions.append("confirm_submit")
        elif material.status == "submitted":
            actions.append("withdraw")
        elif material.status == "needs_correction":
            actions.append("abandon")
    elif is_staff(actor, material):
        if material.status in {"draft", "submitted", "under_review", "needs_correction"}:
            actions.append("check")
        if material.status == "submitted":
            actions.extend(("begin_review", "review"))
        elif material.status == "under_review":
            actions.append("review")
        if actor.role == "admin" and material.status == "rule_unmatched":
            actions.append("mark_rule_available")
    return tuple(actions)


def authorize_transition(
    actor: ActorScope,
    material: MaterialScope,
    action: str,
    target_status: str,
) -> None:
    """Validate one state-changing action or raise a domain error."""
    if action not in allowed_actions(actor, material):
        raise MaterialPolicyError("actor is not allowed to perform this action")
    if (action, material.status, target_status) not in TRANSITIONS:
        raise MaterialPolicyError("material state transition is not allowed")


