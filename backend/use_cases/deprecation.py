"""Explicit retirement gates for legacy score fields and endpoints."""

LEGACY_CONSUMERS = {
    "application_api": "backend/blueprints/application_bp.py",
    "score_api": "backend/blueprints/score_bp.py",
    "certificate_preview": "backend/services/certificates/preview.py",
    "volunteer_automation": "backend/services/automation.py",
}
LEGACY_CONSUMER_DIRECTIONS = {
    "application_api": ("read", "write"),
    "score_api": ("read",),
    "certificate_preview": ("write",),
    "volunteer_automation": ("write",),
}


def legacy_exit_gate(*, consumer_counts, reconciliation_differences,
                     consecutive_clean_runs, backup_verified,
                     automation_regressions_passed):
    blockers = []
    unknown = sorted(set(consumer_counts) - set(LEGACY_CONSUMERS))
    missing = sorted(set(LEGACY_CONSUMERS) - set(consumer_counts))
    active_consumers = sorted(name for name, count in consumer_counts.items() if count)
    if active_consumers:
        blockers.append({"code": "active_consumers", "consumers": active_consumers,
                         "counts": {name: consumer_counts[name] for name in active_consumers}})
    if unknown:
        blockers.append({"code": "untracked_consumers", "consumers": unknown})
    if missing:
        blockers.append({"code": "monitoring_incomplete", "consumers": missing})
    if reconciliation_differences:
        blockers.append({"code": "reconciliation_differences", "count": reconciliation_differences})
    if consecutive_clean_runs < 2:
        blockers.append({"code": "insufficient_clean_runs", "actual": consecutive_clean_runs, "required": 2})
    if not backup_verified:
        blockers.append({"code": "backup_not_verified"})
    if not automation_regressions_passed:
        blockers.append({"code": "automation_regressions_not_verified"})
    return {"can_remove_legacy_data": not blockers, "blockers": blockers}
