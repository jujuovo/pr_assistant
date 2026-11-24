"""Index material history, originals and score lookups for large review queues."""
from alembic import op

revision = '20261123_material_read_indexes'
down_revision = '20261122_faculty_policy_current'
branch_labels = depends_on = None

INDEXES = (
    ('ix_material_event_record', 'material_event', ['record_id', 'id']),
    ('ix_material_attachment_record', 'material_attachment', ['record_id', 'id']),
    ('ix_score_entry_material_status', 'score_entry', ['material_record_id', 'status']),
)


def upgrade():
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns, unique=False)


def downgrade():
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
