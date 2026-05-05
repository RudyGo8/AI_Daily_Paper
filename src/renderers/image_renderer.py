"""封面图渲染模块：使用 Pillow 生成日报封面图片。"""

from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - optional dependency path
    Image = None
    ImageDraw = None
    ImageFont = None


class ImageRenderer:
    """生成日报封面 PNG 图片。"""
    def __init__(self, width: int = 900, height: int = 500) -> None:
        self.width = width
        self.height = height

    def generate_cover(self, title: str, output_path: Path) -> Path | None:
        if Image is None or ImageDraw is None or ImageFont is None:
            return None

        image = Image.new("RGB", (self.width, self.height), color=(24, 36, 72))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        text = title[:80]
        draw.multiline_text((40, 80), text, fill=(255, 255, 255), font=font, spacing=8)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path.as_posix(), format="PNG")
        return output_path

