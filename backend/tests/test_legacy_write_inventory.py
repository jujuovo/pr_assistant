import ast
from pathlib import Path


ROOT=Path(__file__).resolve().parents[2]
BACKEND=ROOT/"backend"


def _is_production(path):
    return "tests" not in path.parts and "migrations" not in path.parts


def test_every_legacy_write_file_is_listed_in_inventory():
    inventory=(ROOT/"docs/legacy-write-inventory.md").read_text(encoding="utf-8")
    discovered=set()
    for path in BACKEND.rglob("*.py"):
        if not _is_production(path): continue
        source=path.read_text(encoding="utf-8")
        tree=ast.parse(source,filename=str(path))
        legacy=False
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in {"Application","update_student_statistics"}:
                legacy=True
            if isinstance(node,(ast.Assign,ast.AugAssign)):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                if any(isinstance(t,ast.Attribute) and t.attr in {"final_score","major_ranking","comprehensive_score"} for t in targets):
                    legacy=True
        if legacy: discovered.add(path.relative_to(ROOT).as_posix())
    assert discovered
    for relative in discovered:
        assert f"`{relative}`" in inventory,relative

