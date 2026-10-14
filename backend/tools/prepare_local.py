"""Create a reproducible local SQLite database; preserve existing application data."""
import os
from pathlib import Path
import argparse
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
LOCAL = BACKEND / 'instance' / 'certificate-local.db'


def main(database_file=None):
    local = Path(database_file).resolve() if database_file else LOCAL
    local.parent.mkdir(parents=True, exist_ok=True)
    fresh = not local.exists()
    os.environ['DATABASE_URL'] = 'sqlite:///' + local.as_posix()
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
        from tools.seed_demo import seed_demo
        seed_demo(with_test_rule=True, with_test_settings=fresh)
        print(f'本地数据库已准备：{local}')
        print('共享三角色测试账号及信息学院规则已准备；已有数据保持不变。')
        print('证书表已创建；识别结果不会修改申请分数。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='准备本地开发SQLite库及共享测试账号')
    parser.add_argument('--database-file', type=Path, help='可选独立测试数据库路径')
    main(parser.parse_args().database_file)
