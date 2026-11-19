"""add immutable competition rule packages

Revision ID: 20261109_competition_package
Revises: 20261108_structured_migration
"""
from alembic import op
import sqlalchemy as sa


revision = "20261109_competition_package"
down_revision = "20261108_structured_migration"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "competition_rule_package",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("package_id", sa.String(length=100), nullable=False),
        sa.Column("cycle_code", sa.Integer(), nullable=False),
        sa.Column("scope_key", sa.String(length=100), nullable=False,
                  server_default="global"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False,
                  server_default="draft"),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("current_scope_key", sa.String(length=220), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("published_by", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("retired_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status in ('draft','current','retired')",
            name="ck_competition_package_status",
        ),
        sa.CheckConstraint(
            "(status = 'current' and current_scope_key is not null) or "
            "(status <> 'current' and current_scope_key is null)",
            name="ck_competition_package_current_key",
        ),
        sa.CheckConstraint("version > 0", name="ck_competition_package_version"),
        sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
        sa.ForeignKeyConstraint(["published_by"], ["user.id"]),
        sa.UniqueConstraint("current_scope_key", name="uq_competition_package_current_scope"),
        sa.UniqueConstraint(
            "cycle_code", "scope_key", "version",
            name="uq_competition_package_scope_version",
        ),
        sa.UniqueConstraint(
            "cycle_code", "scope_key", "digest",
            name="uq_competition_package_scope_digest",
        ),
    )
    with op.batch_alter_table("material_record") as batch:
        batch.add_column(sa.Column("competition_rule_package_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_material_competition_package", "competition_rule_package",
            ["competition_rule_package_id"], ["id"],
        )
        batch.create_index(
            "ix_material_competition_package", ["competition_rule_package_id"]
        )


def downgrade():
    with op.batch_alter_table("material_record") as batch:
        batch.drop_index("ix_material_competition_package")
        batch.drop_constraint("fk_material_competition_package", type_="foreignkey")
        batch.drop_column("competition_rule_package_id")
    op.drop_table("competition_rule_package")
