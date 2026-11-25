"""Guarded test-data reset and formal 2028 competition-package initialization."""

import json
import os
from pathlib import Path

from sqlalchemy import delete, func, select

from extensions import db
from material_models import CompetitionOcrJob, MaterialAttachment, MaterialEvent, MaterialRecord
from models import Rule
from use_cases.competition_rules import load_current_competition_package
from workflow_models import CompetitionRulePackage, ScoreEntry


RESET_CONFIRMATION = "RESET-COMPETITION-2028"


class CompetitionInitializationError(ValueError):
    def __init__(self, message, *, code="competition_initialization_error"):
        super().__init__(message)
        self.code = code


def formal_package_snapshot():
    path = Path(__file__).resolve().parents[1] / "rules" / "competition_2028.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _competition_material_ids():
    return select(MaterialRecord.id).where(MaterialRecord.category == "competition")


def _legacy_competition_application_ids():
    from legacy_models import Application
    return (
        select(Application.id)
        .join(Rule, Application.rule_id == Rule.id)
        .where(Rule.sub_type == "competition")
    )


def preview_competition_reset():
    material_ids = _competition_material_ids()
    legacy_ids = _legacy_competition_application_ids() if "application" in db.metadata.tables else None
    return {
        "competition_ocr_jobs": db.session.scalar(
            select(func.count()).select_from(CompetitionOcrJob).where(
                CompetitionOcrJob.record_id.in_(material_ids)
            )
        ),
        "material_events": db.session.scalar(
            select(func.count()).select_from(MaterialEvent).where(
                MaterialEvent.record_id.in_(material_ids)
            )
        ),
        "material_attachments": db.session.scalar(
            select(func.count()).select_from(MaterialAttachment).where(
                MaterialAttachment.record_id.in_(material_ids)
            )
        ),
        "competition_score_entries": db.session.scalar(
            select(func.count()).select_from(ScoreEntry).where(
                ScoreEntry.category == "competition"
            )
        ),
        "competition_materials": db.session.scalar(
            select(func.count()).select_from(MaterialRecord).where(
                MaterialRecord.category == "competition"
            )
        ),
        "legacy_competition_applications": db.session.scalar(
            select(func.count()).select_from(legacy_ids.subquery())
        ) if legacy_ids is not None else 0,
        "competition_rule_packages": db.session.scalar(
            select(func.count()).select_from(CompetitionRulePackage)
        ),
    }


def reset_and_initialize_competition_2028(
    actor, *, backup_reference, confirmation, dry_run=True, snapshot=None,
    environment_allows_reset=False,
):
    preview = preview_competition_reset()
    if dry_run:
        return {"dry_run": True, "preview": preview, "package": None}
    allowed = environment_allows_reset or os.environ.get(
        "COMPETITION_RESET_ALLOWED"
    ) == "YES"
    if not allowed:
        raise CompetitionInitializationError(
            "competition reset is disabled in this environment",
            code="competition_reset_disabled",
        )
    if confirmation != RESET_CONFIRMATION:
        raise CompetitionInitializationError(
            "explicit reset confirmation is required",
            code="competition_reset_confirmation_required",
        )
    backup = Path(str(backup_reference or ""))
    if not backup.is_absolute() or not backup.is_file() or backup.stat().st_size == 0:
        raise CompetitionInitializationError(
            "a non-empty absolute backup file is required",
            code="competition_backup_required",
        )

    desired = snapshot or formal_package_snapshot()
    desired_digest = CompetitionRulePackage.canonical_digest(desired)
    current = CompetitionRulePackage.query.filter_by(
        cycle_code=2028, scope_key="global", status="current"
    ).one_or_none()
    if current is not None and current.digest == desired_digest and not any(
        preview[key]
        for key in (
            "competition_ocr_jobs", "material_events", "material_attachments",
            "competition_score_entries", "competition_materials",
            "legacy_competition_applications",
        )
    ):
        return {"dry_run": False, "preview": preview, "package": current, "created": False}

    material_ids = _competition_material_ids()
    db.session.execute(delete(CompetitionOcrJob).where(CompetitionOcrJob.record_id.in_(material_ids)))
    db.session.execute(delete(MaterialEvent).where(MaterialEvent.record_id.in_(material_ids)))
    db.session.execute(delete(MaterialAttachment).where(MaterialAttachment.record_id.in_(material_ids)))
    db.session.execute(delete(ScoreEntry).where(ScoreEntry.category == "competition"))
    db.session.execute(delete(MaterialRecord).where(MaterialRecord.category == "competition"))
    if preview["legacy_competition_applications"]:
        from legacy_models import Application
        db.session.execute(delete(Application).where(Application.id.in_(_legacy_competition_application_ids())))
    db.session.execute(delete(CompetitionRulePackage))
    package, created = load_current_competition_package(actor, desired)
    db.session.flush()
    return {"dry_run": False, "preview": preview, "package": package, "created": created}
