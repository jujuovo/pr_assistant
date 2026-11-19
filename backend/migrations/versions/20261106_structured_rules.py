"""add structured matching metadata to rules and versions

Revision ID: 20261106_structured_rules
Revises: 20261106_structured_terms
"""
from alembic import op
import sqlalchemy as sa

revision = "20261106_structured_rules"
down_revision = "20261106_structured_terms"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("rule") as batch:
        batch.add_column(sa.Column("match_terms", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("match_schema_version", sa.String(32), nullable=True))
        batch.add_column(sa.Column("draft_version", sa.Integer(), nullable=False, server_default="1"))
        batch.create_check_constraint("ck_rule_draft_version", "draft_version > 0")
    with op.batch_alter_table("rule_version") as batch:
        batch.add_column(sa.Column("match_terms_digest", sa.String(64), nullable=True))
        batch.add_column(sa.Column("match_schema_version", sa.String(32), nullable=True))
        batch.create_check_constraint(
            "ck_rule_version_match_metadata",
            "(match_terms_digest is null and match_schema_version is null) or "
            "(match_terms_digest is not null and match_schema_version is not null)",
        )


def downgrade():
    with op.batch_alter_table("rule_version") as batch:
        batch.drop_constraint("ck_rule_version_match_metadata", type_="check")
        batch.drop_column("match_schema_version")
        batch.drop_column("match_terms_digest")
    with op.batch_alter_table("rule") as batch:
        batch.drop_constraint("ck_rule_draft_version", type_="check")
        batch.drop_column("draft_version")
        batch.drop_column("match_schema_version")
        batch.drop_column("match_terms")
