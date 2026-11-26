"""Resolve files strictly inside their private storage directory."""

def contained(root, relative):
    path = (root / relative).resolve()
    if path == root or root not in path.parents:
        raise ValueError("证书文件路径越界")
    return path
