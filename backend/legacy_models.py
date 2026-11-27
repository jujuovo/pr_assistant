"""Offline mappings for databases predating the material-only schema. Never import at web startup."""
from extensions import db
from models import get_current_time
from automation_models import utcnow


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.String(20), db.ForeignKey("student.student_id"), nullable=False
    )
    student_name = db.Column(db.String(100), nullable=False)
    # 使用外键关联学院、系和专业
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), nullable=True)
    department_id = db.Column(
        db.Integer, db.ForeignKey("department.id"), nullable=False
    )
    major_id = db.Column(db.Integer, db.ForeignKey("major.id"), nullable=False)
    application_type = db.Column(
        db.String(50), nullable=False
    )  # academic, comprehensive
    applied_at = db.Column(db.DateTime, default=get_current_time)
    self_score = db.Column(db.Float, nullable=True)
    status = db.Column(
        db.String(20), default="pending"
    )  # pending, approved, rejected, draft
    project_name = db.Column(db.String(200), nullable=False)
    award_date = db.Column(db.Date, nullable=True)
    cycle_code = db.Column(db.Integer, nullable=True)
    cycle_policy_version_id = db.Column(
        db.Integer, db.ForeignKey("recommendation_cycle_policy.id"), nullable=True
    )
    description = db.Column(db.Text, nullable=True)
    files = db.Column(db.JSON, nullable=True)  # 存储文件信息的JSON数组
    dynamic_coefficients = db.Column(db.JSON, nullable=True)  # 存储动态系数数据的JSON对象

    # 审核相关字段
    final_score = db.Column(db.Float, nullable=True)  # 最终核定分数
    review_comment = db.Column(db.Text, nullable=True)  # 审核意见
    reviewed_at = db.Column(db.DateTime, nullable=True)  # 审核时间
    reviewed_by = db.Column(db.String(100), nullable=True)  # 审核人

    # 规则关联
    rule_id = db.Column(db.Integer, db.ForeignKey("rule.id"), nullable=True)

    # 关系定义
    faculty = db.relationship("Faculty", backref=db.backref("applications", lazy=True))
    department = db.relationship(
        "Department", backref=db.backref("applications", lazy=True)
    )
    major = db.relationship("Major", backref=db.backref("applications", lazy=True))

    created_at = db.Column(db.DateTime, default=get_current_time)
    updated_at = db.Column(
        db.DateTime, default=get_current_time, onupdate=get_current_time
    )

    def __repr__(self):
        return f"<Application {self.id}>"


class LegacyBackfillBatch(db.Model):
    __tablename__ = "legacy_backfill_batch"
    id = db.Column(db.Integer, primary_key=True)
    batch_key = db.Column(db.String(128), nullable=False, unique=True)
    year = db.Column(db.Integer, nullable=False)
    backup_reference = db.Column(db.String(500), nullable=False)
    cycle_policy_version_id = db.Column(
        db.Integer, db.ForeignKey("recommendation_cycle_policy.id"), nullable=True
    )
    evidence_manifest = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="running")
    processed_count = db.Column(db.Integer, nullable=False, default=0)
    failed_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow)


class LegacyBackfillItem(db.Model):
    __tablename__ = "legacy_backfill_item"
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("legacy_backfill_batch.id"), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey("application.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    result = db.Column(db.JSON, nullable=True)
    error = db.Column(db.String(1000), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    __table_args__ = (db.UniqueConstraint("batch_id", "application_id", name="uq_backfill_item_application"),)


# Offline historical tools also need the two foreign keys that existed in their
# database version. Normal web and worker processes never load these mappings.
from material_models import MaterialRecord
from automation_models import AutomationBatch

MaterialRecord.application_id = db.Column(db.Integer, db.ForeignKey("application.id"))
AutomationBatch.application_id = db.Column(db.Integer, db.ForeignKey("application.id"), unique=True)
