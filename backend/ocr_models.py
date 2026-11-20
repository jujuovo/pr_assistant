"""Private recognition jobs and immutable student-confirmed material associations."""
import uuid
from extensions import db
from automation_models import utcnow


class OCRJob(db.Model):
    __tablename__ = "ocr_job"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=False)
    category = db.Column(db.String(64), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    material_record_id = db.Column(db.Integer, db.ForeignKey("material_record.id"), nullable=True)
    material_version = db.Column(db.Integer, nullable=True)
    attachment_id = db.Column(db.Integer, db.ForeignKey("material_attachment.id"), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="queued")
    report = db.Column(db.JSON)
    error = db.Column(db.Text)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    lease_token = db.Column(db.String(36))
    lease_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (db.Index("ix_ocr_job_queue", "status", "lease_until"),
                      db.Index("ix_ocr_material_version", "material_record_id", "material_version"))


class OCRMaterialLink(db.Model):
    """One OCR job binds once; preserve both suggestions and the confirmation snapshot."""
    __tablename__ = "ocr_material_link"
    job_id = db.Column(db.String(36), db.ForeignKey("ocr_job.id"), primary_key=True)
    material_record_id = db.Column(db.Integer, db.ForeignKey("material_record.id"), nullable=False)
    suggestions = db.Column(db.JSON, nullable=False)
    confirmed_snapshot = db.Column(db.JSON, nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    job = db.relationship("OCRJob")
    __table_args__ = (db.Index("ix_ocr_material_record", "material_record_id"),)
