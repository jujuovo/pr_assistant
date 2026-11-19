"""Check the function-length budget of the automatic recognition flow.

Run from any directory: python -B backend/tools/check_recognition_structure.py
"""
import ast
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
LIMIT = 100


def recognition_files():
    for folder in ('services/recognition', 'services/certificates', 'services/competition_ocr'):
        yield from sorted((BACKEND / folder).rglob('*.py'))
    for name in ('services/automation.py', 'blueprints/automation_bp.py',
                 'blueprints/certificate_bp.py', 'recognition_worker.py'):
        yield BACKEND / name


def main():
    functions = []
    for path in recognition_files():
        tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append((node.end_lineno - node.lineno + 1,
                                  path.relative_to(BACKEND).as_posix(), node.lineno, node.name))
    violations = [entry for entry in functions if entry[0] > LIMIT]
    for length, path, line, name in sorted(violations, reverse=True):
        print(f'{path}:{line} {name}: {length} lines (limit {LIMIT})')
    print(f'{len(functions)} functions checked; maximum {max(entry[0] for entry in functions)} lines; '
          f'{len(violations)} over {LIMIT} lines')
    return bool(violations)


if __name__ == '__main__':
    raise SystemExit(main())
