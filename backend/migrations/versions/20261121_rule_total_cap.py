"""Store an optional cumulative score limit on each rule."""
from alembic import op
import sqlalchemy as sa

revision = "20261121_rule_total_cap"
down_revision = "20261121_certificate_restrict"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("rule", sa.Column("total_score_cap", sa.Numeric(12, 4), nullable=True))


def downgrade():
    with op.batch_alter_table("rule") as batch:
        batch.drop_column("total_score_cap")
