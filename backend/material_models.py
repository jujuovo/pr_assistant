"""五类材料的结构化申报、校方数据和核验记录；不存储加分结果。"""
from extensions import db
from automation_models import utcnow


class MaterialRecord(db.Model):
    __tablename__ = 'material_record'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), db.ForeignKey('student.student_id'), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=True)
    category = db.Column(db.String(32), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(32), nullable=False, default='draft')
    data = db.Column(db.JSON, nullable=False)
    analysis = db.Column(db.JSON, nullable=False)
    check_report = db.Column(db.JSON)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    attachments = db.relationship('MaterialAttachment', backref='record', order_by='MaterialAttachment.id', cascade='all, delete-orphan')
    events = db.relationship('MaterialEvent', backref='record', order_by='MaterialEvent.id')
    __table_args__ = (db.Index('ix_material_owner', 'faculty_id', 'student_id', 'category', 'year'),)


class MaterialAttachment(db.Model):
    __tablename__ = 'material_attachment'
    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey('material_record.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(80), nullable=False, unique=True)
    sha256 = db.Column(db.String(64), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class MaterialEvent(db.Model):
    __tablename__ = 'material_event'
    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey('material_record.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(32), nullable=False)
    details = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)


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
