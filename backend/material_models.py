"""五类材料的结构化申报、校方数据和核验记录；不存储加分结果。"""
from extensions import db
from automation_models import utcnow


class MaterialRecord(db.Model):
    __tablename__ = 'material_record'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), db.ForeignKey('student.student_id'), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty.id'), nullable=False)
    category = db.Column(db.String(32), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    cycle_policy_version_id = db.Column(
        db.Integer, db.ForeignKey('recommendation_cycle_policy.id'), nullable=True
    )
    status = db.Column(db.String(32), nullable=False, default='draft')
    review_stage = db.Column(db.Integer, nullable=False, default=1, server_default='1')
    data = db.Column(db.JSON, nullable=False)
    analysis = db.Column(db.JSON, nullable=False)
    # Evidence extraction, student declarations and normalized matching input are
    # deliberately separate.  Nullable columns preserve the meaning of legacy
    # rows: absence means "not confirmed", never an inferred confirmation.
    ocr_raw_terms = db.Column(db.JSON, nullable=True)
    confirmed_terms = db.Column(db.JSON, nullable=True)
    normalized_terms = db.Column(db.JSON, nullable=True)
    normalization_version = db.Column(db.String(32), nullable=True)
    rule_version_id = db.Column(
        db.Integer, db.ForeignKey('rule_version.id'), nullable=True
    )
    competition_rule_package_id = db.Column(
        db.Integer, db.ForeignKey('competition_rule_package.id'), nullable=True
    )
    competition_duplicate_digest = db.Column(db.String(64), nullable=True)
    competition_work_group_key = db.Column(db.String(64), nullable=True)
    competition_event_group_key = db.Column(db.String(128), nullable=True)
    supersedes_record_id = db.Column(
        db.Integer, db.ForeignKey('material_record.id'), nullable=True
    )
    correction_sequence = db.Column(db.Integer, nullable=False, default=0)
    check_report = db.Column(db.JSON)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    attachments = db.relationship('MaterialAttachment', backref='record', order_by='MaterialAttachment.id', cascade='all, delete-orphan')
    events = db.relationship('MaterialEvent', backref='record', order_by='MaterialEvent.id')
    __table_args__ = (
        db.Index('ix_material_owner', 'faculty_id', 'student_id', 'category', 'year'),
        db.Index('ix_material_rule_state', 'status', 'rule_version_id'),
        db.Index('ix_material_competition_package', 'competition_rule_package_id'),
        db.Index(
            'ix_material_competition_duplicate', 'student_id', 'year',
            'competition_duplicate_digest', unique=True,
        ),
        db.Index('ix_material_competition_work', 'student_id', 'year', 'competition_work_group_key'),
        db.Index('ix_material_competition_event', 'student_id', 'year', 'competition_event_group_key'),
        db.Index('ix_material_correction_chain', 'supersedes_record_id'),
    )


class CompetitionOcrJob(db.Model):
    """Cancelable OCR assistance bound to one exact material version."""

    __tablename__ = 'competition_ocr_job'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String(64), nullable=False, unique=True)
    record_id = db.Column(db.Integer, db.ForeignKey('material_record.id'), nullable=False)
    material_version = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(24), nullable=False, default='queued')
    cancelled = db.Column(db.Boolean, nullable=False, default=False)
    raw_result = db.Column(db.JSON, nullable=True)
    ignored_late_result = db.Column(db.JSON, nullable=True)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (
        db.Index('ix_competition_ocr_record_version', 'record_id', 'material_version'),
        db.CheckConstraint('material_version > 0', name='ck_competition_ocr_material_version'),
        db.CheckConstraint(
            "status in ('queued','running','completed','failed','cancelled','ignored')",
            name='ck_competition_ocr_status',
        ),
    )


class MaterialAttachment(db.Model):
    __tablename__ = 'material_attachment'
    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey('material_record.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(80), nullable=False, unique=True)
    sha256 = db.Column(db.String(64), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (db.Index('ix_material_attachment_record', 'record_id', 'id'),)


class MaterialEvent(db.Model):
    __tablename__ = 'material_event'
    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey('material_record.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(64), nullable=False)
    details = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (db.Index('ix_material_event_record', 'record_id', 'id'),)


class MaterialSource(db.Model):
    """管理员录入的校方/官方核验数据快照；同一来源的新版本保留旧版本。"""
    __tablename__ = 'material_source'
    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty.id'), nullable=False)
    student_id = db.Column(db.String(20), db.ForeignKey('student.student_id'), nullable=False)
    category = db.Column(db.String(32), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    external_id = db.Column(db.String(128), nullable=False)
    revision = db.Column(db.Integer, nullable=False)
    source_name = db.Column(db.String(200), nullable=False)
    source_url = db.Column(db.String(1000), nullable=False)
    data = db.Column(db.JSON, nullable=False)
    digest = db.Column(db.String(64), nullable=False)
    imported_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (db.UniqueConstraint('faculty_id', 'student_id', 'category', 'year', 'external_id', 'revision', name='uq_material_source_revision'),)
