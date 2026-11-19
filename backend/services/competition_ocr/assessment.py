"""Read-only queue and scoring projections; never changes declared facts or scores."""
from flask import current_app
from extensions import db
from material_models import CompetitionOcrJob
from workflow_models import CompetitionRulePackage
from domain.competition_scoring import calculate_competition_candidate, CompetitionScoringError


def latest_job(row):
    return CompetitionOcrJob.query.filter_by(record_id=row.id).order_by(
        CompetitionOcrJob.created_at.desc(), CompetitionOcrJob.id.desc()).first()


def assessment(row):
    if row.category != "competition":
        return None
    job = latest_job(row)
    valid = bool(job and (job.material_version == row.version or
                         (job.raw_result and (job.raw_result == row.ocr_raw_terms or job.raw_result.get("report") == row.ocr_raw_terms))))
    result = job.raw_result if valid and job.status == "completed" else None
    package = db.session.get(CompetitionRulePackage, row.competition_rule_package_id) if row.competition_rule_package_id else None
    declared = row.confirmed_terms or row.data or {}
    mapping = (result or {}).get("mapping") or {}
    evidence = mapping.get("data") or {}
    report = (result or {}).get("report") or {}
    fields = report.get("fields") or {}
    comparisons = []
    for key in ("competition_id", "project_name", "award_date", "award"):
        if evidence.get(key) not in (None, "") and declared.get(key) != evidence[key]:
            comparisons.append({"field": key, "declared": declared.get(key), "recognized": evidence[key]})
    # Only explicit printed stage terms are eligible; province/region names never imply level.
    level = {"全国总决赛":"national", "省级赛":"provincial"}.get(fields.get("stage_as_printed"))
    recognized = {k:evidence[k] for k in ("competition_id", "award") if evidence.get(k)}
    if level:
        recognized["level"] = level
        if declared.get("level") != level:
            comparisons.append({"field":"level", "declared":declared.get("level"), "recognized":level})
    missing = [k for k in ("competition_id", "level", "award") if not recognized.get(k)]
    if not evidence.get("award_date"):
        missing.append("award_date")
    suggested = None
    if result and package and recognized.get("competition_id") and recognized.get("award"):
        try:
            params = {k:declared[k] for k in ("participation_mode", "team_size", "personal_rank", "event_format", "csp_percentile") if k in declared}
            params["level"] = recognized.get("level") or declared.get("level")
            suggested = str(calculate_competition_candidate(package.snapshot, **{k:v for k,v in recognized.items() if k!="level"}, **params).candidate_score)
        except (CompetitionScoringError, TypeError):
            missing.append("scoring_basis")
    family = next((i["event_family"] for i in (package.snapshot["catalog"] if package else [])
                   if i["competition_id"] == declared.get("competition_id")), None)
    if result and report.get("warnings"):
        missing.append("recognition_quality")
    if result and evidence.get("award_date") and package:
        period=package.snapshot["evidence_period"]
        if not period["start"]<=evidence["award_date"]<=period["end"]:
            missing.append("evidence_period");suggested=None
    mature = family in current_app.config.get("OCR_MATURE_EVENT_FAMILIES", ())
    status = job.status if valid else "stale"
    if job and valid and status=="queued":
        from ocr_models import OCRJob
        worker_job=db.session.get(OCRJob,job.job_id)
        if worker_job and worker_job.status=="processing": status="running"
    return {"declared_estimate":(row.analysis or {}).get("candidate_score"),
            "ocr_suggested_score":suggested, "differences":comparisons, "missing_fields":missing,
            "mature_adapter":mature, "requires_teacher_review":True,
            "review_mode":"rule_assisted" if mature and result and not missing and not comparisons else "manual_confirmation",
            "conditional_on_student_facts":["level", "participation_mode", "team_size", "personal_rank", "csp_percentile"],
            "job":({"job_id":job.job_id, "status":status,
                    "error":job.error, "material_version":job.material_version} if job else None),
            "notice":"预估为本项候选分；团队信息等沿用手填申报，仍需核验。最终计入分受审核、去重及上限影响。"}


def workflow_projection(row):
    advice = assessment(row)
    if row.status == "draft":
        status = ((advice or {}).get("job") or {}).get("status")
        state = {"queued":"ocr_queued", "running":"ocr_running", "completed":"ready_to_submit",
                 "failed":"ocr_failed", "stale":"draft"}.get(status)
        if not state:
            state = "ready_to_submit" if row.attachments else "draft"
    else:
        state = {"submitted":"pending_review", "under_review":"pending_review", "scored":"approved",
                 "verified":"approved", "verified_not_eligible":"approved_ineligible"}.get(row.status, row.status)
    return {"workflow_state":state, "ocr_assessment":advice}
