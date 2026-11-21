"""证书识别辅助结果；申请的类别、等级、分数仍由学生和教师决定。"""
from extensions import db
from automation_models import utcnow


class CertificateAssessment(db.Model):
    __tablename__ = "certificate_assessment"
    id = db.Column(db.Integer, primary_key=True)
    # 证书评估是审核依据，不能被旧申请的删除静默带走：
    # CASCADE 会让"删一条 application"顺手清掉评估记录且不留痕，故改为 RESTRICT。
    application_id = db.Column(db.Integer, db.ForeignKey("application.id", ondelete="RESTRICT"), nullable=False, unique=True)
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
    # Let the database reject parent deletion; ORM cascades would erase evidence first.
    application = db.relationship("Application", backref=db.backref(
        "certificate_assessment", uselist=False, passive_deletes="all"))
    __table_args__ = (db.Index("ix_certificate_queue", "status", "lease_until"),)
