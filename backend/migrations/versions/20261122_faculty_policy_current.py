"""Enforce one published scoring policy per faculty and cycle."""
from alembic import op
import sqlalchemy as sa

revision = "20261122_faculty_policy_current"
down_revision = "20261121_faculty_policy"
branch_labels = depends_on = None


def upgrade():
    condition = sa.text("status = 'published'")
    op.create_index("uq_faculty_scoring_policy_current", "faculty_scoring_policy",
                    ["faculty_id", "cycle_code"], unique=True,
                    sqlite_where=condition, postgresql_where=condition)


def downgrade():
    op.drop_index("uq_faculty_scoring_policy_current", table_name="faculty_scoring_policy")
