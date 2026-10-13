"""将项目附带的旧 SQLite 复制为独立运行数据库，再进行增量补齐。"""
import os
from pathlib import Path
import sqlite3
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
LOCAL = BACKEND / 'instance' / 'certificate-local.db'


def main():
    LOCAL.parent.mkdir(exist_ok=True)
    if not LOCAL.exists():
        source = BACKEND / 'instance' / 'gradpush.db'
        if source.exists():
            # SQLite backup API 同时处理 WAL，源库以只读方式打开。
            with sqlite3.connect('file:'+source.as_posix()+'?mode=ro',uri=True) as original:
                with sqlite3.connect(LOCAL) as target:
                    original.backup(target)
            print('已复制项目附带数据库，源库保持原样。')
    os.environ['DATABASE_URL'] = 'sqlite:///' + LOCAL.as_posix()
    from app import app
    from extensions import db
    from sqlalchemy import inspect, text
    # 附带历史 SQLite 只缺少这些兼容字段；不猜测未知数据库的迁移。
    additions = {'system_settings': {'avatar_file_size_limit':'INTEGER DEFAULT 2'},
                 'rule': {'faculty_id':'INTEGER REFERENCES faculty(id)', 'calculation_formula':'JSON'},
                 'application': {'dynamic_coefficients':'JSON'}}
    with app.app_context():
        with db.engine.begin() as connection:
            inspector = inspect(connection)
            for table, columns in additions.items():
                if not inspector.has_table(table):
                    continue
                existing = {c['name'] for c in inspector.get_columns(table)}
                for name, declaration in columns.items():
                    if name not in existing:
                        connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {declaration}'))
        db.create_all()
        inspector = inspect(db.engine)
        missing = {t.name:[c.name for c in t.columns if c.name not in {v['name'] for v in inspector.get_columns(t.name)}]
                   for t in db.metadata.sorted_tables}
        if any(missing.values()):
            raise RuntimeError(f'本地数据库存在未适配字段，请检查：{missing}')
        from models import SystemSettings
        if not SystemSettings.query.first():
            db.session.add(SystemSettings())
            db.session.commit()
        print(f'本地数据库已准备：{LOCAL}')
        print('证书表已创建；识别结果不会修改申请分数。')


if __name__ == '__main__':
    main()
