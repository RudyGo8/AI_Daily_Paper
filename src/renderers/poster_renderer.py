"""海报图渲染模块：使用 Pillow 生成 AI 日报信息海报。

海报包含：标题区、日期、分类板块（每类显示 top-N 条目摘要）、一句话总结。
使用 Windows 系统中文字体，不可用时回退到 Pillow 默认字体。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - optional dependency path
    Image = None
    ImageDraw = None
    ImageFont = None

from src.models.schemas import DailyArticle, NewsItem


@dataclass
class PosterSection:
    """海报中的一个内容板块。"""
    index: int
    title: str
    bullets: list[str]


class PosterRenderer:
    """生成 AI 日报信息海报。"""
    CATEGORY_TITLES = {
        "模型发布": "模型动态",
        "产品动态": "产品更新",
        "研究进展": "研究前沿",
        "工具框架": "工具框架",
        "融资并购": "融资 / 行业",
        "行业事件": "行业事件",
    }

    CATEGORY_ORDER = [
        "模型发布",
        "产品动态",
        "工具框架",
        "研究进展",
        "融资并购",
        "行业事件",
    ]

    def __init__(self, width: int = 1080, section_limit: int = 3) -> None:
        self.width = width
        self.section_limit = section_limit

    def generate_poster(self, article: DailyArticle, output_path: Path) -> Path | None:
        if Image is None or ImageDraw is None or ImageFont is None:
            return None

        sections = self._build_sections(article)
        if not sections:
            sections = [PosterSection(index=1, title="今日速递", bullets=["今日暂无符合条件的 AI 动态。"])]

        fonts = self._load_fonts()
        line_height = fonts["body"].size + 10
        title_height = fonts["section"].size + 24
        bullet_wrap_width = 44
        section_gap = 22
        padding = 28
        header_height = 170

        content_height = 0
        for section in sections:
            bullet_lines = sum(
                max(1, len(self._wrap_text(bullet, bullet_wrap_width)))
                for bullet in section.bullets
            )
            content_height += title_height + bullet_lines * line_height + 36
            content_height += section_gap

        height = header_height + content_height + padding + 60
        image = Image.new("RGB", (self.width, height), color=(6, 16, 46))
        draw = ImageDraw.Draw(image)

        self._draw_background(draw, height)
        self._draw_header(draw, article, fonts)

        cursor_y = header_height
        for section in sections:
            section_height = self._draw_section(
                draw=draw,
                section=section,
                top=cursor_y,
                fonts=fonts,
                bullet_wrap_width=bullet_wrap_width,
                line_height=line_height,
            )
            cursor_y += section_height + section_gap

        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path.as_posix(), format="PNG")
        return output_path

    def _build_sections(self, article: DailyArticle) -> list[PosterSection]:
        sections: list[PosterSection] = []
        index = 1
        for category in self.CATEGORY_ORDER:
            items = article.categories.get(category, [])
            if not items:
                continue
            bullets = [self._make_bullet(item) for item in items[: self.section_limit]]
            sections.append(
                PosterSection(
                    index=index,
                    title=self.CATEGORY_TITLES.get(category, category),
                    bullets=bullets,
                )
            )
            index += 1

        digest = article.digest.strip()
        if digest:
            sections.append(
                PosterSection(
                    index=index,
                    title="一句话总结",
                    bullets=[digest],
                )
            )
        return sections

    def _make_bullet(self, item: NewsItem) -> str:
        base = item.ai_summary or item.summary or item.title
        compact = " ".join(base.split()).strip()
        if len(compact) > 70:
            compact = compact[:67].rstrip("，。 ;") + "..."
        if item.cluster_size > 1 and len(item.merged_sources) > 1:
            source_note = " / ".join(item.merged_sources[:3])
            return f"{compact} ({source_note})"
        return compact

    def _draw_background(self, draw: ImageDraw.ImageDraw, height: int) -> None:
        draw.rectangle((0, 0, self.width, height), fill=(7, 14, 40))
        draw.rectangle((0, 0, self.width, 18), fill=(61, 76, 255))
        draw.rectangle((0, 18, self.width, 22), fill=(0, 228, 255))
        for y in range(0, height, 120):
            draw.line((0, y, self.width, y), fill=(18, 34, 82), width=1)
        for x in range(0, self.width, 140):
            draw.line((x, 0, x + 60, height), fill=(11, 24, 68), width=1)

    def _draw_header(
        self,
        draw: ImageDraw.ImageDraw,
        article: DailyArticle,
        fonts: dict[str, ImageFont.FreeTypeFont | ImageFont.ImageFont],
    ) -> None:
        draw.rounded_rectangle((24, 24, self.width - 24, 146), radius=22, fill=(11, 20, 56), outline=(50, 92, 255), width=3)
        draw.rounded_rectangle((40, 40, 122, 122), radius=18, fill=(25, 44, 120), outline=(92, 233, 255), width=3)
        draw.text((58, 58), "AI", font=fonts["logo"], fill=(255, 255, 255))
        draw.text((150, 48), "全球 AI 日报", font=fonts["title"], fill=(255, 255, 255))
        draw.text((150, 92), "AI Daily Brief", font=fonts["subtitle"], fill=(166, 211, 255))

        date_label = article.target_date.isoformat()
        date_box = (self.width - 330, 48, self.width - 54, 112)
        draw.rounded_rectangle(date_box, radius=16, fill=(19, 29, 74), outline=(95, 129, 255), width=2)
        draw.text((date_box[0] + 28, date_box[1] + 18), date_label, font=fonts["date"], fill=(255, 255, 255))

        issue = f"Vol.{article.target_date.strftime('%m%d')}"
        issue_w = self._text_width(draw, issue, fonts["tag"])
        tag_box = (self.width - 180, 116, self.width - 54, 148)
        draw.rounded_rectangle(tag_box, radius=14, fill=(74, 40, 210), outline=(117, 214, 255), width=2)
        draw.text((tag_box[0] + (tag_box[2] - tag_box[0] - issue_w) / 2, tag_box[1] + 6), issue, font=fonts["tag"], fill=(255, 255, 255))

    def _draw_section(
        self,
        draw: ImageDraw.ImageDraw,
        section: PosterSection,
        top: int,
        fonts: dict[str, ImageFont.FreeTypeFont | ImageFont.ImageFont],
        bullet_wrap_width: int,
        line_height: int,
    ) -> int:
        left = 26
        right = self.width - 26
        badge_w = 96

        wrapped_bullets = [self._wrap_text(bullet, bullet_wrap_width) for bullet in section.bullets]
        bullet_line_count = sum(max(1, len(lines)) for lines in wrapped_bullets)
        section_height = 88 + bullet_line_count * line_height

        draw.rounded_rectangle((left, top, right, top + section_height), radius=24, fill=(244, 248, 255), outline=(31, 98, 255), width=4)
        draw.rounded_rectangle((left + 12, top + 18, left + 12 + badge_w, top + 70), radius=16, fill=(90, 82, 255))
        draw.text((left + 28, top + 24), f"{section.index:02d}", font=fonts["section_index"], fill=(255, 255, 255))
        draw.text((left + 140, top + 22), section.title, font=fonts["section"], fill=(18, 33, 89))

        cursor_y = top + 72
        bullet_x = left + 146
        for lines in wrapped_bullets:
            draw.text((bullet_x, cursor_y), "•", font=fonts["bullet"], fill=(14, 92, 255))
            local_y = cursor_y - 2
            for line in lines:
                draw.text((bullet_x + 26, local_y), line, font=fonts["body"], fill=(26, 40, 78))
                local_y += line_height
            cursor_y = local_y + 4

        return section_height

    @staticmethod
    def _wrap_text(text: str, width: int) -> list[str]:
        compact = " ".join(text.split()).strip()
        if not compact:
            return [""]
        lines: list[str] = []
        current = ""
        for char in compact:
            tentative = current + char
            if len(tentative) > width:
                lines.append(current)
                current = char
            else:
                current = tentative
        if current:
            lines.append(current)
        return lines

    @staticmethod
    def _text_width(
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    ) -> float:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    def _load_fonts(self) -> dict[str, ImageFont.FreeTypeFont | ImageFont.ImageFont]:
        return {
            "logo": self._load_font(34, bold=True),
            "title": self._load_font(36, bold=True),
            "subtitle": self._load_font(24),
            "date": self._load_font(24, bold=True),
            "tag": self._load_font(20, bold=True),
            "section_index": self._load_font(30, bold=True),
            "section": self._load_font(34, bold=True),
            "body": self._load_font(24),
            "bullet": self._load_font(26, bold=True),
        }

    def _load_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = []
        if bold:
            candidates.extend(
                [
                    Path("C:/Windows/Fonts/msyhbd.ttc"),
                    Path("C:/Windows/Fonts/simhei.ttf"),
                    Path("C:/Windows/Fonts/arialbd.ttf"),
                ]
            )
        candidates.extend(
            [
                Path("C:/Windows/Fonts/msyh.ttc"),
                Path("C:/Windows/Fonts/simsun.ttc"),
                Path("C:/Windows/Fonts/arial.ttf"),
            ]
        )
        for candidate in candidates:
            if candidate.exists():
                try:
                    return ImageFont.truetype(candidate.as_posix(), size=size)
                except OSError:
                    continue
        return ImageFont.load_default()
