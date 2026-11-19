"""add competition evidence, OCR and score explanation fields

Revision ID: 20261109_competition_evidence
Revises: 20261109_competition_package
"""
from alembic import op
import sqlalchemy as sa


revision = "20261109_competition_evidence"
down_revision = "20261109_competition_package"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("material_record") as batch:
        batch.add_column(sa.Column("competition_duplicate_digest", sa.String(64), nullable=True))
        batch.add_column(sa.Column("competition_work_group_key", sa.String(64), nullable=True))
        batch.add_column(sa.Column("competition_event_group_key", sa.String(128), nullable=True))
        batch.create_index(
            "ix_material_competition_duplicate",
            ["student_id", "year", "competition_duplicate_digest"], unique=True,
        )
        batch.create_index(
            "ix_material_competition_work",
            ["student_id", "year", "competition_work_group_key"],
        )
        batch.create_index(
            "ix_material_competition_event",
            ["student_id", "year", "competition_event_group_key"],
        )
    op.create_table(
        "competition_ocr_job",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(64), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("material_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("cancelled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("raw_result", sa.JSON(), nullable=True),
        sa.Column("ignored_late_result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("material_version > 0", name="ck_competition_ocr_material_version"),
        sa.CheckConstraint(
            "status in ('queued','running','completed','failed','cancelled','ignored')",
            name="ck_competition_ocr_status",
        ),
        sa.ForeignKeyConstraint(["record_id"], ["material_record.id"]),
        sa.UniqueConstraint("job_id", name="uq_competition_ocr_job_id"),
    )
    op.create_index(
        "ix_competition_ocr_record_version", "competition_ocr_job",
        ["record_id", "material_version"],
    )
    with op.batch_alter_table("score_entry") as batch:
        batch.alter_column("rule_version_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("competition_rule_package_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("candidate_score", sa.Numeric(12, 4), nullable=True))
        batch.add_column(sa.Column("competition_work_group_key", sa.String(64), nullable=True))
        batch.add_column(sa.Column("competition_event_group_key", sa.String(128), nullable=True))
        batch.add_column(sa.Column("exclusion_stage", sa.String(64), nullable=True))
        batch.add_column(sa.Column("exclusion_basis", sa.JSON(), nullable=True))
        batch.create_foreign_key(
            "fk_score_competition_package", "competition_rule_package",
            ["competition_rule_package_id"], ["id"],
        )
        batch.create_index(
            "ix_score_competition_package_student",
            ["competition_rule_package_id", "student_id", "year"],
        )
        batch.create_index(
            "ix_score_competition_work",
            ["student_id", "year", "competition_work_group_key"],
        )
        batch.create_index(
            "ix_score_competition_event",
            ["student_id", "year", "competition_event_group_key"],
        )
        batch.create_check_constraint(
            "ck_score_entry_rule_authority",
            "rule_version_id is not null or competition_rule_package_id is not null",
        )


def downgrade():
    with op.batch_alter_table("score_entry") as batch:
        batch.drop_constraint("ck_score_entry_rule_authority", type_="check")
        batch.drop_index("ix_score_competition_event")
        batch.drop_index("ix_score_competition_work")
        batch.drop_index("ix_score_competition_package_student")
        batch.drop_constraint("fk_score_competition_package", type_="foreignkey")
        batch.drop_column("exclusion_basis")
        batch.drop_column("exclusion_stage")
        batch.drop_column("competition_event_group_key")
        batch.drop_column("competition_work_group_key")
        batch.drop_column("candidate_score")
        batch.drop_column("competition_rule_package_id")
        batch.alter_column("rule_version_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index("ix_competition_ocr_record_version", table_name="competition_ocr_job")
    op.drop_table("competition_ocr_job")
    with op.batch_alter_table("material_record") as batch:
        batch.drop_index("ix_material_competition_event")
        batch.drop_index("ix_material_competition_work")
        batch.drop_index("ix_material_competition_duplicate")
        batch.drop_column("competition_event_group_key")
        batch.drop_column("competition_work_group_key")
        batch.drop_column("competition_duplicate_digest")
