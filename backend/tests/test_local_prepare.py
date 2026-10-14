"""Fresh checkout preparation must work without a historical database snapshot."""
import os
import bcrypt
from pathlib import Path
import sqlite3
import subprocess
import sys


def test_prepare_new_database_and_preserve_existing_data(tmp_path):
    root = Path(__file__).resolve().parents[2]
    database = tmp_path / '含 空格' / 'fresh.db'
    environment = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    command = [sys.executable, '-B', str(root / 'backend/tools/prepare_local.py'), '--database-file', str(database)]
    for iteration in range(2):
        result = subprocess.run(command, cwd=tmp_path, env=environment, capture_output=True, text=True, encoding='utf-8', timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        with sqlite3.connect(database) as connection:
            assert connection.execute('select count(*) from user').fetchone()[0] == 3
            assert connection.execute('select count(*) from rule').fetchone()[0] == 1
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
