"""Compatibility review version and append-only audit projection."""
from alembic import op
import sqlalchemy as sa

revision = '20261126_application_review'
down_revision = '20261126_review_stages'
branch_labels = depends_on = None


def upgrade():
    op.add_column('application', sa.Column('review_version', sa.Integer(), nullable=False, server_default=sa.text('1')))
    op.add_column('application', sa.Column('review_history', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('application') as batch:
        batch.drop_column('review_history')
        batch.drop_column('review_version')
