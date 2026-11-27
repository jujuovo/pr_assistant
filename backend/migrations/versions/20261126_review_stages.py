"""Add review stages without changing existing material results or scores."""
from alembic import op
import sqlalchemy as sa

revision = '20261126_review_stages'
down_revision = '20261123_material_read_indexes'
branch_labels = depends_on = None


def upgrade():
    for table in ('material_record', 'application'):
        op.add_column(table, sa.Column('review_stage', sa.Integer(), nullable=False,
                                      server_default=sa.text('1')))


def downgrade():
    for table in ('application', 'material_record'):
        with op.batch_alter_table(table) as batch:
            batch.drop_column('review_stage')
