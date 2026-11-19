"""add auditable competition rule package drafts

Revision ID: 20261110_rule_package_drafts
Revises: 20261109_competition_notify
"""
from alembic import op
import sqlalchemy as sa


revision = "20261110_rule_package_drafts"
down_revision = "20261109_competition_notify"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("competition_rule_package") as batch:
        batch.add_column(sa.Column("draft_revision", sa.Integer(), nullable=False,
                                   server_default="1"))
        batch.add_column(sa.Column("source_package_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("source_digest", sa.String(64), nullable=True))
        batch.add_column(sa.Column("source_summary", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("updated_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        batch.create_foreign_key(
            "fk_competition_package_source", "competition_rule_package",
            ["source_package_id"], ["id"],
        )
        batch.create_foreign_key(
            "fk_competition_package_updated_by", "user", ["updated_by"], ["id"]
        )
        batch.create_check_constraint(
            "ck_competition_package_draft_revision", "draft_revision > 0"
        )
        batch.create_check_constraint(
            "ck_competition_package_source_pair",
            "(source_package_id is null and source_digest is null) or "
            "(source_package_id is not null and source_digest is not null)",
        )
    # Preserve existing package identity and references. Existing published 2028
    # packages become revision 1 with no synthetic source ancestry.
    op.execute(
        "UPDATE competition_rule_package SET updated_at = created_at "
        "WHERE updated_at IS NULL"
    )
    with op.batch_alter_table("competition_rule_package") as batch:
        batch.alter_column("updated_at", existing_type=sa.DateTime(), nullable=False)


def downgrade():
    with op.batch_alter_table("competition_rule_package") as batch:
        batch.drop_constraint("ck_competition_package_source_pair", type_="check")
        batch.drop_constraint("ck_competition_package_draft_revision", type_="check")
        batch.drop_constraint("fk_competition_package_updated_by", type_="foreignkey")
        batch.drop_constraint("fk_competition_package_source", type_="foreignkey")
        batch.drop_column("updated_at")
        batch.drop_column("updated_by")
        batch.drop_column("source_summary")
        batch.drop_column("source_digest")
        batch.drop_column("source_package_id")
        batch.drop_column("draft_revision")
