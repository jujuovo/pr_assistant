import argparse
from pathlib import Path

from src.lab_io import json_text
from .batch import run_batch
from .catalog import CATEGORIES
from .engine import PaddleEngine
from .http_api import create_server
from .service import CompetitionOCR


def main():
    parser = argparse.ArgumentParser(description="分类证件 OCR 实验")
    parser.add_argument("--model-root", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("categories")
    one = commands.add_parser("recognize")
    one.add_argument("category", choices=CATEGORIES)
    one.add_argument("image", type=Path)
    batch = commands.add_parser("samples")
    batch.add_argument("category", choices=["all", *CATEGORIES])
    batch.add_argument("--output", type=Path, required=True)
    batch.add_argument("--save-images", action="store_true", help="保存原图、OCR 定位图和去水印对照")
    api = commands.add_parser("serve")
    api.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.command == "categories":
        print(json_text([vars(item) for item in CATEGORIES.values()]))
        return 0
    service = CompetitionOCR(PaddleEngine(args.model_root))
    if args.command == "recognize":
        print(json_text(service.recognize(args.image, args.category)))
    elif args.command == "samples":
        selected = CATEGORIES.values() if args.category == "all" else [CATEGORIES[args.category]]
        return run_batch(service, selected, args.output, args.save_images)
    else:
        with create_server(service, args.port) as server:
            print(f"本机 OCR 接口：http://127.0.0.1:{server.server_port}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
