"""材料自动化的独立表；已有申请表和前端字段保持兼容。"""
from datetime import datetime, timezone
from extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AutomationPolicy(db.Model):
    __tablename__ = "automation_policy"
    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    revision = db.Column(db.Integer, nullable=False, default=1)
    config = db.Column(db.JSON, nullable=False)
    __table_args__ = (db.UniqueConstraint("faculty_id", "year", name="uq_auto_policy_year"),)


class AutomationBatch(db.Model):
    __tablename__ = "automation_batch"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), db.ForeignKey("student.student_id"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    material_type = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(24), nullable=False, default="queued")
    application_id = db.Column(db.Integer, db.ForeignKey("application.id"), unique=True)
    policy_snapshot = db.Column(db.JSON)
    score_snapshot = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    lease_token = db.Column(db.String(36))
    lease_until = db.Column(db.DateTime)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    error = db.Column(db.Text)
    version = db.Column(db.Integer, nullable=False, default=1)
    items = db.relationship("AutomationItem", backref="batch", order_by="AutomationItem.id")
    __table_args__ = (db.Index("ix_auto_queue", "status", "lease_until"),
                      db.Index("ix_auto_student_year", "student_id", "year", "status"))


class AutomationItem(db.Model):
    __tablename__ = "automation_item"
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("automation_batch.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(80))
    sha256 = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(24), nullable=False, default="queued")
    duplicate_of = db.Column(db.Integer, db.ForeignKey("automation_item.id"))
    report = db.Column(db.JSON)
    raw_ocr = db.Column(db.JSON)
    claimed_hours = db.Column(db.Numeric(12, 4))
    confirmed_hours = db.Column(db.Numeric(12, 4))
    activity_dates = db.Column(db.JSON)
    submitted = db.Column(db.Boolean, nullable=False, default=False)
    review_comment = db.Column(db.Text)
    error = db.Column(db.Text)
    __table_args__ = (db.Index("ix_auto_items_batch", "batch_id"),)


class AutomationFingerprint(db.Model):
    """唯一索引同时防止并发批次抢占同一活动；审核拒绝也不删除上传记录。"""
    __tablename__ = "automation_fingerprint"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), db.ForeignKey("student.student_id"), nullable=False)
    kind = db.Column(db.String(24), nullable=False)
    value = db.Column(db.String(64), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("automation_item.id"), nullable=False)
    __table_args__ = (db.UniqueConstraint("student_id", "kind", "value", name="uq_auto_fingerprint"),)


class AutomationReview(db.Model):
    __tablename__ = "automation_review"
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("automation_batch.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    details = db.Column(db.JSON, nullable=False)
