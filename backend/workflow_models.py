"""Persistent models owned by the material-to-ranking workflow."""

import hashlib
import json

from sqlalchemy import event

from automation_models import utcnow
from extensions import db


class RecommendationCyclePolicy(db.Model):
    """Immutable policy version for the single global recommendation cycle."""

    __tablename__ = "recommendation_cycle_policy"

    id = db.Column(db.Integer, primary_key=True)
    cycle_code = db.Column(db.Integer, nullable=False)
    version = db.Column(db.Integer, nullable=False)
    display_name = db.Column(db.String(50), nullable=False)
    eligible_award_start_date = db.Column(db.Date, nullable=False)
    eligible_award_end_date = db.Column(db.Date, nullable=False)
    boundary = db.Column(db.String(20), nullable=False, default="inclusive")
    digest = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="draft")
    # NULL values do not conflict in supported databases; the sole active row uses 1.
    active_marker = db.Column(db.Integer, nullable=True, unique=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    activated_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    activated_at = db.Column(db.DateTime, nullable=True)
    retired_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint("cycle_code", "version", name="uq_cycle_policy_version"),
        db.UniqueConstraint("cycle_code", "digest", name="uq_cycle_policy_digest"),
        db.CheckConstraint(
            "cycle_code >= 2000 and cycle_code <= 2100",
            name="ck_cycle_policy_code",
        ),
        db.CheckConstraint(
            "eligible_award_end_date >= eligible_award_start_date",
            name="ck_cycle_policy_dates",
        ),
        db.CheckConstraint(
            "boundary = 'inclusive'", name="ck_cycle_policy_boundary"
        ),
        db.CheckConstraint(
            "status in ('draft','active','retired')", name="ck_cycle_policy_status"
        ),
        db.CheckConstraint(
            "active_marker is null or active_marker = 1",
            name="ck_cycle_policy_active_marker",
        ),
    )

    @staticmethod
    def canonical_digest(cycle_code, start_date, end_date):
        payload = {
            "boundary": "inclusive",
            "cycle_code": int(cycle_code),
            "eligible_award_end_date": end_date.isoformat(),
            "eligible_award_start_date": start_date.isoformat(),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


class CompetitionRulePackage(db.Model):
    """Versioned, immutable competition catalog and policy aggregate."""

    __tablename__ = "competition_rule_package"

    id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(db.String(100), nullable=False)
    cycle_code = db.Column(db.Integer, nullable=False)
    scope_key = db.Column(db.String(100), nullable=False, default="global")
    version = db.Column(db.Integer, nullable=False)
    draft_revision = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), nullable=False, default="draft")
    snapshot = db.Column(db.JSON, nullable=False)
    digest = db.Column(db.String(64), nullable=False)
    # Only a current package carries this deterministic key.  NULL retired/draft
    # values do not conflict, while the unique key works on SQLite and Postgres.
    current_scope_key = db.Column(db.String(220), nullable=True, unique=True)
    source_package_id = db.Column(
        db.Integer, db.ForeignKey("competition_rule_package.id"), nullable=True
    )
    source_digest = db.Column(db.String(64), nullable=True)
    source_summary = db.Column(db.JSON, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    published_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    published_at = db.Column(db.DateTime, nullable=True)
    retired_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "cycle_code", "scope_key", "version",
            name="uq_competition_package_scope_version",
        ),
        db.UniqueConstraint(
            "cycle_code", "scope_key", "digest",
            name="uq_competition_package_scope_digest",
        ),
        db.CheckConstraint(
            "status in ('draft','current','retired')",
            name="ck_competition_package_status",
        ),
        db.CheckConstraint(
            "(status = 'current' and current_scope_key is not null) or "
            "(status <> 'current' and current_scope_key is null)",
            name="ck_competition_package_current_key",
        ),
        db.CheckConstraint("version > 0", name="ck_competition_package_version"),
        db.CheckConstraint(
            "draft_revision > 0", name="ck_competition_package_draft_revision"
        ),
        db.CheckConstraint(
            "(source_package_id is null and source_digest is null) or "
            "(source_package_id is not null and source_digest is not null)",
            name="ck_competition_package_source_pair",
        ),
    )

    @staticmethod
    def canonical_digest(snapshot):
        payload = json.dumps(
            snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def current_key(cycle_code, scope_key="global"):
        return f"{int(cycle_code)}:{scope_key}"


class RuleVersion(db.Model):
    """An immutable scoring-rule snapshot used by auditable score entries."""

    __tablename__ = "rule_version"

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("rule.id"), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="published")
    snapshot = db.Column(db.JSON, nullable=False)
    digest = db.Column(db.String(64), nullable=False)
    match_terms_digest = db.Column(db.String(64), nullable=True)
    match_schema_version = db.Column(db.String(32), nullable=True)
    published_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    published_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint("rule_id", "version", name="uq_rule_version_number"),
        db.UniqueConstraint("rule_id", "digest", name="uq_rule_version_digest"),
        db.CheckConstraint(
            "(match_terms_digest is null and match_schema_version is null) or "
            "(match_terms_digest is not null and match_schema_version is not null)",
            name="ck_rule_version_match_metadata",
        ),
    )

    @staticmethod
    def canonical_digest(snapshot):
        payload = json.dumps(
            snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class ScoreEntry(db.Model):
    """A traceable score fact derived from one source revision and rule."""

    __tablename__ = "score_entry"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.String(20), db.ForeignKey("student.student_id"), nullable=False
    )
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    cycle_policy_version_id = db.Column(
        db.Integer, db.ForeignKey("recommendation_cycle_policy.id"), nullable=True
    )
    score_group = db.Column(db.String(32), nullable=False)
    category = db.Column(db.String(32), nullable=False)
    source_type = db.Column(db.String(32), nullable=False)
    source_id = db.Column(db.String(128), nullable=False)
    source_revision = db.Column(db.Integer, nullable=False)
    material_record_id = db.Column(
        db.Integer, db.ForeignKey("material_record.id"), nullable=True
    )
    rule_version_id = db.Column(
        db.Integer, db.ForeignKey("rule_version.id"), nullable=True
    )
    competition_rule_package_id = db.Column(
        db.Integer, db.ForeignKey("competition_rule_package.id"), nullable=True
    )
    candidate_score = db.Column(db.Numeric(12, 4), nullable=True)
    competition_work_group_key = db.Column(db.String(64), nullable=True)
    competition_event_group_key = db.Column(db.String(128), nullable=True)
    exclusion_stage = db.Column(db.String(64), nullable=True)
    exclusion_basis = db.Column(db.JSON, nullable=True)
    raw_score = db.Column(db.Numeric(12, 4), nullable=False)
    adjusted_score = db.Column(db.Numeric(12, 4), nullable=False)
    effective_score = db.Column(db.Numeric(12, 4), nullable=False)
    included = db.Column(db.Boolean, nullable=False, default=True)
    exclusion_reason = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active")
    invalidated_reason = db.Column(db.String(500), nullable=True)
    invalidated_at = db.Column(db.DateTime, nullable=True)
    idempotency_key = db.Column(db.String(128), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "source_type",
            "source_id",
            "source_revision",
            "rule_version_id",
            name="uq_score_entry_source_revision_rule",
        ),
        db.CheckConstraint(
            "status in ('active','invalidated')", name="ck_score_entry_status"
        ),
        db.CheckConstraint(
            "source_revision > 0", name="ck_score_entry_source_revision_positive"
        ),
        db.CheckConstraint(
            "rule_version_id is not null or competition_rule_package_id is not null",
            name="ck_score_entry_rule_authority",
        ),
        db.Index(
            "ix_score_competition_package_student",
            "competition_rule_package_id", "student_id", "year",
        ),
        db.Index(
            "ix_score_competition_work", "student_id", "year",
            "competition_work_group_key",
        ),
        db.Index(
            "ix_score_competition_event", "student_id", "year",
            "competition_event_group_key",
        ),
        db.Index(
            "ix_score_entry_recalculation_scope",
            "faculty_id", "year", "status", "student_id",
        ),
        db.Index("ix_score_entry_material_status", "material_record_id", "status"),
    )


class ScoreOverrideAudit(db.Model):
    """Append-only explanation for an authorized manual score override."""

    __tablename__ = "score_override_audit"
    id = db.Column(db.Integer, primary_key=True)
    score_entry_id = db.Column(db.Integer, db.ForeignKey("score_entry.id"), nullable=False)
    source_type = db.Column(db.String(32), nullable=False)
    source_id = db.Column(db.String(128), nullable=False)
    source_version = db.Column(db.Integer, nullable=False)
    rule_version_id = db.Column(db.Integer, db.ForeignKey("rule_version.id"), nullable=False)
    automatic_score = db.Column(db.Numeric(12, 4), nullable=False)
    override_score = db.Column(db.Numeric(12, 4), nullable=False)
    difference = db.Column(db.Numeric(12, 4), nullable=False)
    reason = db.Column(db.String(1000), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint("score_entry_id", name="uq_score_override_entry"),
        db.CheckConstraint("override_score >= 0", name="ck_score_override_nonnegative"),
    )


class StudentScoreSnapshot(db.Model):
    """A reproducible student score projection for one academic year."""

    __tablename__ = "student_score_snapshot"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.String(20), db.ForeignKey("student.student_id"), nullable=False
    )
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    version = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="current")
    academic_base_score = db.Column(db.Numeric(12, 4), nullable=False)
    academic_weight = db.Column(db.Numeric(8, 4), nullable=False)
    specialty_raw_score = db.Column(db.Numeric(12, 4), nullable=False)
    specialty_score = db.Column(db.Numeric(12, 4), nullable=False)
    performance_raw_score = db.Column(db.Numeric(12, 4), nullable=False)
    performance_score = db.Column(db.Numeric(12, 4), nullable=False)
    comprehensive_score = db.Column(db.Numeric(12, 4), nullable=False)
    input_digest = db.Column(db.String(64), nullable=False)
    rule_version_ids = db.Column(db.JSON, nullable=False)
    cycle_policy_version_ids = db.Column(db.JSON, nullable=False, default=list)
    breakdown = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "year", "version", name="uq_student_score_snapshot_version"
        ),
        db.UniqueConstraint(
            "student_id", "year", "input_digest", name="uq_student_score_snapshot_input"
        ),
        db.CheckConstraint(
            "status in ('current','superseded')", name="ck_student_score_snapshot_status"
        ),
        db.Index(
            "ix_score_snapshot_current_scope",
            "faculty_id", "year", "status", "student_id",
        ),
    )


class RankingBatch(db.Model):
    """A versioned draft or official ranking for one explicit scope."""

    __tablename__ = "ranking_batch"

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    major_id = db.Column(db.Integer, db.ForeignKey("major.id"), nullable=True)
    scope_type = db.Column(db.String(32), nullable=False)
    scope_definition = db.Column(db.JSON, nullable=False)
    cutoff_at = db.Column(db.DateTime, nullable=False)
    rule_version_ids = db.Column(db.JSON, nullable=False)
    score_precision = db.Column(db.Integer, nullable=False, default=4)
    status = db.Column(db.String(20), nullable=False, default="draft")
    version = db.Column(db.Integer, nullable=False, default=1)
    input_digest = db.Column(db.String(64), nullable=False)
    predecessor_batch_id = db.Column(
        db.Integer, db.ForeignKey("ranking_batch.id"), nullable=True
    )
    source_summary = db.Column(db.JSON, nullable=True)
    stale_reason = db.Column(db.String(500), nullable=True)
    correction_reason = db.Column(db.String(1000), nullable=True)
    correction_requested_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    correction_requested_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    frozen_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    frozen_at = db.Column(db.DateTime, nullable=True)
    published_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    published_at = db.Column(db.DateTime, nullable=True)
    withdrawn_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    withdrawn_at = db.Column(db.DateTime, nullable=True)
    withdrawal_reason = db.Column(db.String(1000), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "year", "faculty_id", "scope_type", "input_digest",
            name="uq_ranking_batch_scope_input",
        ),
        db.CheckConstraint(
            "status in ('draft','stale','frozen','correction_required','published','withdrawn')",
            name="ck_ranking_batch_status",
        ),
        db.CheckConstraint(
            "score_precision >= 0 and score_precision <= 8",
            name="ck_ranking_batch_precision",
        ),
        db.Index(
            "ix_ranking_batch_workflow_scope",
            "year", "faculty_id", "major_id", "status",
        ),
    )


class RankingEntry(db.Model):
    """One student's frozen score and rank inside a ranking batch."""

    __tablename__ = "ranking_entry"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer, db.ForeignKey("ranking_batch.id", ondelete="CASCADE"), nullable=False
    )
    student_id = db.Column(
        db.String(20), db.ForeignKey("student.student_id"), nullable=False
    )
    score_snapshot_id = db.Column(
        db.Integer, db.ForeignKey("student_score_snapshot.id"), nullable=True
    )
    frozen_score = db.Column(db.Numeric(12, 4), nullable=True)
    rank = db.Column(db.Integer, nullable=True)
    display_order = db.Column(db.Integer, nullable=False)
    eligible = db.Column(db.Boolean, nullable=False, default=True)
    exclusion_reason = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint("batch_id", "student_id", name="uq_ranking_entry_student"),
        db.UniqueConstraint("batch_id", "display_order", name="uq_ranking_entry_order"),
        db.CheckConstraint("rank is null or rank > 0", name="ck_ranking_entry_rank"),
        db.CheckConstraint("display_order > 0", name="ck_ranking_entry_order"),
    )


class RankingStateEvent(db.Model):
    __tablename__ = "ranking_state_event"
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("ranking_batch.id"), nullable=False)
    from_status = db.Column(db.String(32), nullable=True)
    to_status = db.Column(db.String(32), nullable=False)
    reason = db.Column(db.String(1000), nullable=True)
    batch_version = db.Column(db.Integer, nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class RankingCommand(db.Model):
    """Idempotency ledger shared by every ranking lifecycle command."""
    __tablename__ = "ranking_command"
    id = db.Column(db.Integer, primary_key=True)
    idempotency_key = db.Column(db.String(128), nullable=False, unique=True)
    action = db.Column(db.String(32), nullable=False)
    request_digest = db.Column(db.String(64), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey("ranking_batch.id"), nullable=False)
    result = db.Column(db.JSON, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class ScoreRecalculationCommand(db.Model):
    """Idempotent audit result for one scope-bound score rebuild command."""
    __tablename__ = "score_recalculation_command"
    id = db.Column(db.Integer, primary_key=True)
    idempotency_key = db.Column(db.String(128), nullable=False, unique=True)
    request_digest = db.Column(db.String(64), nullable=False)
    preview_digest = db.Column(db.String(64), nullable=False)
    scope = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    result = db.Column(db.JSON, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class MaterialReviewCommand(db.Model):
    """Durable idempotency result for one material review command."""

    __tablename__ = "material_review_command"

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(
        db.Integer, db.ForeignKey("material_record.id"), nullable=False
    )
    idempotency_key = db.Column(db.String(128), nullable=False)
    request_digest = db.Column(db.String(64), nullable=False)
    result = db.Column(db.JSON, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (
        db.UniqueConstraint(
            "record_id", "idempotency_key", name="uq_material_review_command_key"
        ),
    )


class CompetitionRulePackageCommand(db.Model):
    """Idempotency ledger for package lifecycle commands."""

    __tablename__ = "competition_rule_package_command"
    id = db.Column(db.Integer, primary_key=True)
    command_type = db.Column(db.String(32), nullable=False)
    idempotency_key = db.Column(db.String(128), nullable=False)
    request_digest = db.Column(db.String(64), nullable=False)
    package_id = db.Column(
        db.Integer, db.ForeignKey("competition_rule_package.id"), nullable=True
    )
    result = db.Column(db.JSON, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (
        db.UniqueConstraint(
            "command_type", "idempotency_key",
            name="uq_competition_package_command_key",
        ),
    )


class CompetitionRulePackageRevision(db.Model):
    """Immutable content snapshot for one editable package draft revision."""

    __tablename__ = "competition_rule_package_revision"
    id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(
        db.Integer, db.ForeignKey("competition_rule_package.id"), nullable=False
    )
    revision = db.Column(db.Integer, nullable=False)
    snapshot = db.Column(db.JSON, nullable=False)
    digest = db.Column(db.String(64), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (
        db.UniqueConstraint(
            "package_id", "revision", name="uq_competition_package_revision"
        ),
    )


class CompetitionNotificationIntent(db.Model):
    """Retryable post-commit notification; never authoritative workflow state."""
    __tablename__ = "competition_notification_intent"
    id = db.Column(db.Integer, primary_key=True)
    intent_key = db.Column(db.String(160), nullable=False, unique=True)
    student_id = db.Column(db.String(20), db.ForeignKey("student.student_id"), nullable=False)
    material_record_id = db.Column(db.Integer, db.ForeignKey("material_record.id"), nullable=False)
    event_type = db.Column(db.String(64), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    attempts = db.Column(db.Integer, nullable=False, default=0)
    last_error = db.Column(db.String(1000), nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (
        db.CheckConstraint("status in ('pending','sent')", name="ck_competition_notification_status"),
        db.CheckConstraint("attempts >= 0", name="ck_competition_notification_attempts"),
    )


class ReviewScoringCommand(db.Model):
    """Idempotency record shared by every evidence review/scoring source."""

    __tablename__ = "review_scoring_command"

    id = db.Column(db.Integer, primary_key=True)
    source_type = db.Column(db.String(32), nullable=False)
    source_id = db.Column(db.String(128), nullable=False)
    source_version = db.Column(db.Integer, nullable=False)
    idempotency_key = db.Column(db.String(128), nullable=False)
    request_digest = db.Column(db.String(64), nullable=False)
    result = db.Column(db.JSON, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "source_type", "source_id", "idempotency_key",
            name="uq_review_scoring_source_key",
        ),
        db.CheckConstraint(
            "source_version > 0", name="ck_review_scoring_source_version"
        ),
    )


class RankingExportAudit(db.Model):
    __tablename__ = "ranking_export_audit"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("ranking_batch.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    entry_count = db.Column(db.Integer, nullable=False)
    purpose = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)






class StructuredMaterialMigrationBatch(db.Model):
    __tablename__ = "structured_material_migration_batch"
    id = db.Column(db.Integer, primary_key=True)
    batch_key = db.Column(db.String(128), nullable=False, unique=True)
    backup_reference = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="running")
    processed_count = db.Column(db.Integer, nullable=False, default=0)
    failed_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class StructuredMaterialMigrationItem(db.Model):
    __tablename__ = "structured_material_migration_item"
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey(
        "structured_material_migration_batch.id"), nullable=False)
    material_record_id = db.Column(db.Integer, db.ForeignKey("material_record.id"), nullable=False)
    status = db.Column(db.String(32), nullable=False)
    result = db.Column(db.JSON, nullable=True)
    error = db.Column(db.String(1000), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (db.UniqueConstraint(
        "batch_id", "material_record_id", name="uq_structured_migration_item_material"
    ),)


def _reject_rule_version_mutation(_mapper, _connection, _target):
    raise ValueError("published rule versions are immutable")


def _protect_cycle_policy_fields(_mapper, _connection, target):
    from sqlalchemy import inspect

    state = inspect(target)
    immutable = (
        "cycle_code",
        "version",
        "display_name",
        "eligible_award_start_date",
        "eligible_award_end_date",
        "boundary",
        "digest",
        "created_by",
        "created_at",
    )
    if any(state.attrs[name].history.has_changes() for name in immutable):
        raise ValueError("cycle policy versions are immutable")


def _protect_competition_package_fields(_mapper, _connection, target):
    from sqlalchemy import inspect

    state = inspect(target)
    immutable = [
        "package_id", "cycle_code", "scope_key", "version",
        "source_package_id", "source_digest", "source_summary",
        "created_by", "created_at",
    ]
    # Draft content is versioned through CompetitionRulePackageRevision. Once
    # published/current or retired, content and revision become immutable too.
    if target.status != "draft":
        immutable.extend(("snapshot", "digest", "draft_revision"))
    if any(state.attrs[name].history.has_changes() for name in immutable):
        raise ValueError("published competition rule packages are immutable")


event.listen(RuleVersion, "before_update", _reject_rule_version_mutation)
event.listen(RuleVersion, "before_delete", _reject_rule_version_mutation)
event.listen(RecommendationCyclePolicy, "before_update", _protect_cycle_policy_fields)
event.listen(RecommendationCyclePolicy, "before_delete", _reject_rule_version_mutation)
event.listen(CompetitionRulePackage, "before_update", _protect_competition_package_fields)
event.listen(CompetitionRulePackage, "before_delete", _reject_rule_version_mutation)


def _reject_ranking_entry_mutation(_mapper, _connection, _target):
    raise ValueError("ranking entries are immutable; regenerate from authoritative sources")


event.listen(RankingEntry, "before_update", _reject_ranking_entry_mutation)
event.listen(RankingEntry, "before_delete", _reject_ranking_entry_mutation)



class FacultyScoringPolicy(db.Model):
    __tablename__ = "faculty_scoring_policy"
    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    cycle_code = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="draft")
    revision = db.Column(db.Integer, nullable=False, default=1)
    source_id = db.Column(db.Integer, db.ForeignKey("faculty_scoring_policy.id"))
    sections = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        db.Index(
            "uq_faculty_scoring_policy_current", "faculty_id", "cycle_code", unique=True,
            sqlite_where=db.text("status = 'published'"),
            postgresql_where=db.text("status = 'published'"),
        ),
    )
