"""Run a whole set of samples and retain incremental results."""
from src.lab_io import IMAGE_EXTENSIONS, OUTPUTS, SAMPLES, json_text, save_json


def _plan(selected):
    for spec in selected:
        folder = SAMPLES / spec.sample_folder
        paths = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
        if not paths:
            raise ValueError(f"找不到 {spec.name} 样本")
        for path in paths:
            if not path.resolve().is_relative_to(folder.resolve()):
                raise ValueError(f"样本路径越界：{path.name}")
            yield spec, path


def run_batch(service, selected, output, save_images=False):
    output = output.resolve()
    if not output.is_relative_to(OUTPUTS.resolve()) or output.suffix.lower() != ".json":
        raise ValueError("批处理输出必须是 outputs 下的新 JSON 文件")
    planned = list(_plan(selected))
    image_root = output.with_name(output.stem + "-images")
    if save_images and image_root.exists():
        raise FileExistsError(f"图片目录已存在：{image_root}")
    summary = {"total": len(planned), "status": "running", "results": []}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json_text(summary))
    if save_images:
        image_root.mkdir()
    for spec, path in planned:
        relative = path.relative_to(SAMPLES)
        image_dir = image_root / relative if save_images else None
        try:
            if image_dir is None:
                result = service.recognize(path, spec.key)
            else:
                result = service.recognize(path, spec.key, image_dir=image_dir)
                result["images"] = {name: (image_dir / filename).relative_to(output.parent).as_posix()
                                    for name, filename in result["images"].items()}
        except Exception as exc:
            result = {"category": spec.key, "status": "failed", "error": str(exc)}
        summary["results"].append({"sample": relative.as_posix(), **result})
        save_json(output, summary)
        print(f"{spec.key} / {path.name}: {result['status']}", flush=True)
    failed = sum(row["status"] == "failed" for row in summary["results"])
    summary.update(status="completed_with_errors" if failed else "completed", failed=failed)
    save_json(output, summary)
    return int(bool(failed))
