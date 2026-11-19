"""Opt-in evidence capture for CLI runs; HTTP calls stay temporary."""
from pathlib import Path

from PIL import ImageDraw

from services.certificates.watermark_filter import valid_polygon


def save_overlay(image, page, path):
    rendered = image.copy()
    draw = ImageDraw.Draw(rendered)
    polygons = page.get("rec_polys")
    for points in polygons if polygons is not None else ():
        if valid_polygon(points):
            vertices = [(float(x), float(y)) for x, y in points]
            draw.line(vertices + vertices[:1], fill=(0, 157, 219), width=max(2, min(image.size) // 350))
    rendered.save(path)


class ImageArtifacts:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.files = {}

    def original(self, payload, suffix):
        path = self.directory / ("original" + suffix)
        path.write_bytes(payload)
        self.files["original"] = path.name

    def save_image(self, name, image):
        self._save(name, image.save)

    def overlay(self, name, image, page):
        self._save(name, lambda path: save_overlay(image, page, path))

    def _save(self, name, write):
        path = self.directory / (name + ".png")
        write(path)
        self.files[name] = path.name
