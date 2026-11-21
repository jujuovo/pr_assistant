"""Rehearse the certificate FK repair on a consistent SQLite copy, never the source.

This deliberately does not stamp alembic_version or apply unrelated migrations.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

BACKEND = Path(__file__).resolve().parents[1]


def backup_database(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise ValueError('源数据库不存在')
    if source == destination or destination.exists():
        raise ValueError('副本必须使用未占用的新路径，禁止覆盖已有数据库')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive reservation prevents accidentally overwriting a pre-existing file.
    with destination.open('xb'):
        pass
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as origin:
        with sqlite3.connect(destination) as copy:
            origin.backup(copy)
    return destination


def fingerprints(connection):
    result = {}
    for table in sa.inspect(connection).get_table_names():
        escaped = connection.dialect.identifier_preparer.quote(table)
        rows = connection.exec_driver_sql('SELECT * FROM ' + escaped).all()
        # Values stay local; only counts and digests are emitted to the report.
        serialized = sorted(json.dumps(list(row), ensure_ascii=False, default=str) for row in rows)
        result[table] = {'count': len(rows), 'sha256': hashlib.sha256(
            '\n'.join(serialized).encode('utf-8')).hexdigest()}
    return result


def rehearse(source, destination):
    copy = backup_database(source, destination)
    engine = sa.create_engine(sa.URL.create('sqlite', database=str(copy)))
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql('PRAGMA foreign_keys=ON')
            connection.commit()
            before = fingerprints(connection)
            preexisting = len(connection.exec_driver_sql('PRAGMA foreign_key_check').all())
            connection.commit()
            path = BACKEND / 'migrations/versions/20261121_certificate_restrict.py'
            spec = importlib.util.spec_from_file_location('certificate_restrict_rehearsal', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            original_fk = sa.inspect(connection).get_foreign_keys('certificate_assessment')
            connection.commit()
            with connection.begin():
                with Operations.context(MigrationContext.configure(connection)):
                    module.upgrade()
                    module.upgrade()  # Constraint operation must be safely repeatable.
                if fingerprints(connection) != before:
                    raise RuntimeError('副本数据核对失败；源数据库未修改，请保留副本排查')
                current_fk = sa.inspect(connection).get_foreign_keys('certificate_assessment')
                relevant = [fk for fk in current_fk if fk['constrained_columns'] == ['application_id']]
                if len(relevant) != 1 or relevant[0]['options'].get('ondelete') != 'RESTRICT':
                    raise RuntimeError('副本外键核对失败')
                violations = len(connection.exec_driver_sql('PRAGMA foreign_key_check').all())
                if violations != preexisting:
                    raise RuntimeError('副本外键异常数量发生变化')
            return {'source': str(Path(source).resolve()), 'copy': str(copy),
                    'source_opened_readonly': True, 'data_unchanged': True,
                    'before_foreign_keys': original_fk, 'after_foreign_keys': current_fk,
                    'foreign_key_violations': violations, 'tables': before,
                    'alembic_version_unchanged': True,
                    'scope': 'constraint rehearsal only; not a production upgrade'}
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=BACKEND / 'outputs' /
                        ('legacy-upgrade-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.db'))
    args = parser.parse_args()
    try:
        print(json.dumps(rehearse(args.source, args.output), ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, sa.exc.SQLAlchemyError, sqlite3.Error) as error:
        print(json.dumps({'error': str(error), 'source_not_modified': True}, ensure_ascii=False))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
