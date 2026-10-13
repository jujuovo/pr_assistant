"""证书识别辅助结果；申请的类别、等级、分数仍由学生和教师决定。"""
from extensions import db
from automation_models import utcnow


class CertificateAssessment(db.Model):
    __tablename__ = "certificate_assessment"
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("application.id", ondelete="CASCADE"), nullable=False, unique=True)
    project_key = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="queued")
    claims = db.Column(db.JSON, nullable=False)
    sources = db.Column(db.JSON, nullable=False)
    artifact_key = db.Column(db.String(36), nullable=False)
    report = db.Column(db.JSON)
    error = db.Column(db.Text)
    lease_token = db.Column(db.String(36))
    lease_until = db.Column(db.DateTime)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    application = db.relationship("Application", backref=db.backref("certificate_assessment", uselist=False, cascade="all, delete-orphan"))
    __table_args__ = (db.Index("ix_certificate_queue", "status", "lease_until"),)
