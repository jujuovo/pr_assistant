"""Loopback-only HTTP interface for local integration experiments."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

from .catalog import CATEGORIES
from .service import MAX_BYTES


def create_server(service, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, payload):
            data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if urlsplit(self.path).path == "/api/ocr/categories":
                self.reply(200, {"categories": [
                    {"key": item.key, "name": item.name, "kind": item.kind} for item in CATEGORIES.values()
                ]})
            else:
                self.reply(404, {"error": "接口不存在"})

        def do_POST(self):
            parts = urlsplit(self.path).path.split("/")
            if len(parts) != 5 or parts[:3] != ["", "api", "ocr"] or parts[4] != "recognize" or parts[3] not in CATEGORIES:
                self.reply(404, {"error": "接口或类别不存在"})
                return
            if self.headers.get("Transfer-Encoding"):
                self.reply(400, {"error": "请上传完整图片并提供 Content-Length"})
                return
            if self.headers.get_content_type() not in {"application/octet-stream", "image/jpeg", "image/png",
                                                        "image/webp", "image/bmp", "image/tiff"}:
                self.reply(415, {"error": "请求体必须是原始图片字节"})
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
                if length <= 0:
                    raise ValueError()
            except ValueError:
                self.reply(400, {"error": "无效的 Content-Length"})
                return
            if length > MAX_BYTES:
                self.reply(413, {"error": "图片不得超过 10 MB"})
                return
            try:
                self.connection.settimeout(10)
                data = self.rfile.read(length)
                if len(data) != length:
                    raise ValueError("图片上传不完整")
                result = service.recognize_bytes(data, parts[3])
            except TimeoutError:
                self.reply(408, {"error": "图片上传超时"})
            except ValueError as exc:
                self.reply(400, {"error": str(exc)})
            except Exception:
                self.reply(500, {"error": "OCR 模型不可用或识别失败，请检查本机模型和输入"})
            else:
                self.reply(200, result)

    return HTTPServer(("127.0.0.1", port), Handler)
