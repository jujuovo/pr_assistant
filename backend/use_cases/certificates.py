"""Compatibility adapter from certificate Application review to the unified use case."""

from extensions import db
from material_models import MaterialRecord
from use_cases.materials import MaterialUseCaseError, review_material
from workflow_models import MaterialReviewCommand, RuleVersion


def review_certificate_application(user, application, payload):
    from use_cases.staged_review import assert_final_review
    assert_final_review(user, application)
    if not isinstance(payload, dict):
        raise MaterialUseCaseError("请求体必须为JSON对象")
    allowed = {"status", "reviewComment", "idempotency_key", "override_score", "override_reason",
               "finalScore", "overrideReason", "review_version"}
    if set(payload) - allowed:
        raise MaterialUseCaseError("证书审核请求包含不支持字段")
    if "finalScore" in payload:
        if "override_score" in payload:
            raise MaterialUseCaseError("不能同时提交 finalScore 和 override_score")
        legacy_reason = payload.get("overrideReason")
        if not isinstance(legacy_reason, str) or not legacy_reason.strip():
            raise MaterialUseCaseError(
                "旧 finalScore 已弃用；人工改写必须提供 overrideReason",
                code="legacy_final_score_requires_reason", status_code=400,
            )
        payload = dict(payload, override_score=payload["finalScore"],
                       override_reason=legacy_reason)
    status = payload.get("status")
    decisions = {
        "approved": "verified",
        "rejected": "needs_correction",
        "needs_correction": "needs_correction",
    }
    if status not in decisions:
        raise MaterialUseCaseError("证书审核状态无效")
    if not application.cycle_code or not application.cycle_policy_version_id:
        raise MaterialUseCaseError(
            "证书申请缺少固定周期", code="cycle_policy_missing", status_code=409
        )
    row = MaterialRecord.query.filter_by(application_id=application.id).first()
    if row is None:
        published = None
        if application.rule_id:
            published = (
                RuleVersion.query.filter_by(
                    rule_id=application.rule_id, status="published"
                ).order_by(RuleVersion.version.desc()).first()
            )
            if published and published.snapshot.get("cycle_code") != application.cycle_code:
                published = None
        row = MaterialRecord(
            student_id=application.student_id,
            faculty_id=application.faculty_id,
            application_id=application.id,
            category="competition",
            year=application.cycle_code,
            cycle_policy_version_id=application.cycle_policy_version_id,
            status="submitted", review_stage=application.review_stage,
            data={"award_date": application.award_date.isoformat() if application.award_date else None},
            analysis={"source": "certificate_preview_compatibility"},
            ocr_raw_terms=certificate.claims.get("ocr_raw_terms") if (
                certificate := application.certificate_assessment) else None,
            confirmed_terms=certificate.claims.get("confirmed_terms") if certificate else None,
            normalized_terms=certificate.claims.get("normalized_terms") if certificate else None,
            normalization_version=certificate.claims.get("normalization_version") if certificate else None,
            rule_version_id=published.id if published else None,
            version=1,
        )
        db.session.add(row)
        db.session.flush()
    key = payload.get("idempotency_key") or f"certificate:{application.id}:{row.version}:{status}"
    comment = payload.get("reviewComment", "")
    previous = MaterialReviewCommand.query.filter_by(
        record_id=row.id, idempotency_key=key
    ).first()
    review_version = (
        previous.result.get("version", row.version) - 1 if previous else row.version
    )
    reviewed, replayed = review_material(
        user, row, review_version, decisions[status], comment, key,
        payload.get("override_score"), payload.get("override_reason"),
    )
    if status != "approved":
        application.status = 'needs_correction' if status == 'rejected' else status
        application.final_score = None
    command = MaterialReviewCommand.query.filter_by(
        record_id=reviewed.id, idempotency_key=key
    ).one()
    scoring_status = command.result["scoring"]["scoring_status"]
    if scoring_status == "verified_not_eligible":
        # Compatibility projection: verified evidence is not a material rejection.
        application.status = "approved"
        application.final_score = 0
    result = {
        "application_id": application.id,
        "material_record_id": reviewed.id,
        "status": application.status,
        "cycle_code": application.cycle_code,
        "cycle_policy_version_id": application.cycle_policy_version_id,
        "replayed": replayed,
        **command.result["scoring"],
    }
    if result["scoring_status"] == "needs_rule":
        result["code"] = "needs_rule"
    return result
