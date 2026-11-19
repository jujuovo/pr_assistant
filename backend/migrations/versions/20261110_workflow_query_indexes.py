"""add target-dialect workflow query indexes

Revision ID: 20261110_workflow_indexes
Revises: 20261110_score_recalc
"""
from alembic import op


revision = "20261110_workflow_indexes"
down_revision = "20261110_score_recalc"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_score_entry_recalculation_scope",
        "score_entry",
        ["faculty_id", "year", "status", "student_id"],
    )
    op.create_index(
        "ix_score_snapshot_current_scope",
        "student_score_snapshot",
        ["faculty_id", "year", "status", "student_id"],
    )
    op.create_index(
        "ix_ranking_batch_workflow_scope",
        "ranking_batch",
        ["year", "faculty_id", "major_id", "status"],
    )


def downgrade():
    op.drop_index("ix_ranking_batch_workflow_scope", table_name="ranking_batch")
    op.drop_index("ix_score_snapshot_current_scope", table_name="student_score_snapshot")
    op.drop_index("ix_score_entry_recalculation_scope", table_name="score_entry")
