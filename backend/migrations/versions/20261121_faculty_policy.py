"""Faculty and cycle scoped scoring policy drafts."""
from alembic import op
import sqlalchemy as sa

revision = "20261121_faculty_policy"
down_revision = "20261121_rule_total_cap"
branch_labels = depends_on = None


def upgrade():
    op.create_table("faculty_scoring_policy",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("faculty_id", sa.Integer, sa.ForeignKey("faculty.id"), nullable=False),
        sa.Column("cycle_code", sa.Integer, nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("faculty_scoring_policy.id")),
        sa.Column("sections", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False))


def downgrade():
    op.drop_table("faculty_scoring_policy")
