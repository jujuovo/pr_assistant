import ast
import importlib
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
PACKAGES = ("domain", "use_cases")
FORBIDDEN_IMPORT_ROOTS = {"flask"}
FORBIDDEN_NAMES = {"request", "jsonify"}


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module.split(".", 1)[0]


def test_domain_and_use_case_modules_import_without_flask_transport_dependencies():
    checked = []
    for package in PACKAGES:
        for path in sorted((BACKEND / package).glob("*.py")):
            checked.append(path)
            assert not (set(_imports(path)) & FORBIDDEN_IMPORT_ROOTS), path
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            used_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            assert not (used_names & FORBIDDEN_NAMES), path
            importlib.import_module(f"{package}.{path.stem}")
    assert checked


def test_review_entry_and_tests_reuse_use_case_without_blueprint_business_imports():
    material_blueprint = (BACKEND / "blueprints/material_bp.py").read_text(encoding="utf-8")
    assert "review_material(" in material_blueprint
    for path in sorted((BACKEND / "tests").glob("test_*review*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = {
            node.module for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not any(name.startswith("blueprints.") for name in imports), path
    for path in sorted((BACKEND / "use_cases").glob("*.py")):
        assert not any(name == "blueprints" for name in _imports(path)), path

