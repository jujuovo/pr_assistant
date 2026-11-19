"""Fresh checkout preparation must work without a historical database snapshot."""
import os
import bcrypt
import json
from pathlib import Path
import sqlite3
import subprocess
import sys


def test_prepare_new_database_and_preserve_existing_data(tmp_path):
    root = Path(__file__).resolve().parents[2]
    database = tmp_path / '含 空格' / 'fresh.db'
    environment = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    command = [sys.executable, '-B', str(root / 'backend/tools/prepare_local.py'), '--database-file', str(database)]
    package_digest = None
    for iteration in range(2):
        result = subprocess.run(command, cwd=tmp_path, env=environment, capture_output=True, text=True, encoding='utf-8', timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        with sqlite3.connect(database) as connection:
            assert connection.execute('select count(*) from user').fetchone()[0] == 3
            assert connection.execute('select count(*) from rule').fetchone()[0] == 1
            assert connection.execute('select count(*) from rule_version').fetchone()[0] == 1
            assert connection.execute('select count(*) from recommendation_cycle_policy where active_marker = 1').fetchone()[0] == 1
            assert connection.execute('select cycle_code from recommendation_cycle_policy where active_marker = 1').fetchone()[0] == 2028
            assert connection.execute("select json_extract(snapshot, '$.cycle_code') from rule_version").fetchone()[0] == 2026
            package = connection.execute(
                "select cycle_code, scope_key, status, digest, "
                "json_array_length(snapshot, '$.catalog'), "
                "json_type(snapshot, '$.field_schema') "
                "from competition_rule_package where status = 'current'"
            ).fetchall()
            assert len(package) == 1
            assert package[0][0:3] == (2028, 'global', 'current')
            assert package[0][4:] == (28, 'object')
            assert connection.execute(
                "select count(*) from competition_rule_package "
                "where status = 'current' and cycle_code <> 2028"
            ).fetchone()[0] == 0
            if package_digest is None:
                package_digest = package[0][3]
            else:
                assert package[0][3] == package_digest
            assert connection.execute('select count(*) from faculty').fetchone()[0] == 1
            assert connection.execute('select application_start from system_settings').fetchone()[0].startswith('2026-10-01')
            if iteration == 0:
                stored = connection.execute("select password from user where username = 'student001'").fetchone()[0]
                assert bcrypt.checkpw(b'demo123', stored.encode())
                connection.execute("update student set academic_score = 91")
                connection.execute("update user set password = 'preserve-test-value' where username = 'student001'")
            else:
                assert connection.execute('select academic_score from student').fetchone()[0] == 91
                assert connection.execute("select password from user where username = 'student001'").fetchone()[0] == 'preserve-test-value'


def run_prepare(root, cwd, database, package_file=None):
    environment = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    command = [
        sys.executable, '-B', str(root / 'backend/tools/prepare_local.py'),
        '--database-file', str(database),
    ]
    if package_file is not None:
        command.extend(['--competition-package-file', str(package_file)])
    return subprocess.run(
        command, cwd=cwd, env=environment, capture_output=True, text=True,
        encoding='utf-8', timeout=60,
    )


def test_prepare_removes_fresh_database_when_package_source_is_missing_or_invalid(tmp_path):
    root = Path(__file__).resolve().parents[2]
    for name, source, expected in (
        ('missing', tmp_path / 'missing.json', 'competition_package_source_missing'),
        ('invalid-json', tmp_path / 'invalid.json', 'competition_package_source_invalid'),
        ('invalid-rule', tmp_path / 'invalid-rule.json', 'invalid_competition_package'),
    ):
        if name == 'invalid-json':
            source.write_text('{not-json', encoding='utf-8')
        elif name == 'invalid-rule':
            source.write_text('{}', encoding='utf-8')
        database = tmp_path / f'{name}.db'
        result = run_prepare(root, tmp_path, database, source)
        assert result.returncode != 0
        assert expected in result.stdout + result.stderr
        assert not database.exists(), 'fresh failure must not leave an unusable SQLite file'


def test_prepare_rolls_back_when_a_different_current_package_exists(tmp_path):
    root = Path(__file__).resolve().parents[2]
    database = tmp_path / 'conflict.db'
    first = run_prepare(root, tmp_path, database)
    assert first.returncode == 0, first.stdout + first.stderr
    with sqlite3.connect(database) as connection:
        original_digest = connection.execute(
            "select digest from competition_rule_package where status = 'current'"
        ).fetchone()[0]

    source = json.loads(
        (root / 'backend/rules/competition_2028.json').read_text(encoding='utf-8')
    )
    source['package_id'] = 'conflicting-local-package'
    conflicting = tmp_path / 'conflicting.json'
    conflicting.write_text(json.dumps(source, ensure_ascii=False), encoding='utf-8')

    second = run_prepare(root, tmp_path, database, conflicting)

    assert second.returncode != 0
    assert 'competition_package_already_current' in second.stdout + second.stderr
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "select cycle_code, scope_key, digest from competition_rule_package "
            "where status = 'current'"
        ).fetchall()
        assert rows == [(2028, 'global', original_digest)]
        assert connection.execute('select count(*) from user').fetchone()[0] == 3
