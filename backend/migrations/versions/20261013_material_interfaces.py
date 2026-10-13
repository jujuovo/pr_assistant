"""五类材料接口的数据表，不改写成绩和加分表。"""
from alembic import op
import sqlalchemy as sa

revision='20261013_materials'
down_revision='20261013_certificate'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('material_record',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('student_id',sa.String(20),sa.ForeignKey('student.student_id'),nullable=False),
        sa.Column('faculty_id',sa.Integer(),sa.ForeignKey('faculty.id'),nullable=False),
        sa.Column('application_id',sa.Integer(),sa.ForeignKey('application.id')),
        sa.Column('category',sa.String(32),nullable=False),sa.Column('year',sa.Integer(),nullable=False),
        sa.Column('status',sa.String(32),nullable=False),sa.Column('data',sa.JSON(),nullable=False),
        sa.Column('analysis',sa.JSON(),nullable=False),sa.Column('check_report',sa.JSON()),
        sa.Column('version',sa.Integer(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.Column('updated_at',sa.DateTime(),nullable=False))
    op.create_index('ix_material_owner','material_record',['faculty_id','student_id','category','year'])
    op.create_table('material_attachment',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('record_id',sa.Integer(),sa.ForeignKey('material_record.id'),nullable=False),
        sa.Column('filename',sa.String(255),nullable=False),sa.Column('stored_name',sa.String(80),nullable=False,unique=True),
        sa.Column('sha256',sa.String(64),nullable=False),sa.Column('size',sa.Integer(),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_table('material_event',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('record_id',sa.Integer(),sa.ForeignKey('material_record.id'),nullable=False),
        sa.Column('actor_id',sa.Integer(),sa.ForeignKey('user.id'),nullable=False),
        sa.Column('action',sa.String(32),nullable=False),sa.Column('details',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_table('material_source',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('faculty_id',sa.Integer(),sa.ForeignKey('faculty.id'),nullable=False),
        sa.Column('student_id',sa.String(20),sa.ForeignKey('student.student_id'),nullable=False),
        sa.Column('category',sa.String(32),nullable=False),sa.Column('year',sa.Integer(),nullable=False),
        sa.Column('external_id',sa.String(128),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('source_name',sa.String(200),nullable=False),sa.Column('source_url',sa.String(1000),nullable=False),
        sa.Column('data',sa.JSON(),nullable=False),sa.Column('digest',sa.String(64),nullable=False),
        sa.Column('imported_by',sa.Integer(),sa.ForeignKey('user.id'),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('faculty_id','student_id','category','year','external_id','revision',name='uq_material_source_revision'))


def downgrade():
    op.drop_table('material_source')
    op.drop_table('material_event')
    op.drop_table('material_attachment')
    op.drop_table('material_record')
