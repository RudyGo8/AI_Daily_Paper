"""HTML 渲染模块：将 Markdown 日报转换为带样式的 HTML 页面。

支持双轨转换：
  1. markdown 库 + BeautifulSoup 清洗（完整功能）
  2. 手写逐行解析器 + HTML 实体编码（纯标准库 fallback）
"""

from __future__ import annotations

from html import escape
import re

try:
    import markdown
except ImportError:  # pragma: no cover - optional dependency path
    markdown = None

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - optional dependency path
    BeautifulSoup = None


class HtmlRenderer:
    """将 Markdown 日报转换为带微信风格样式的 HTML 页面。"""
    def render(
        self,
        markdown_text: str | None = None,
        title: str = "",
        markdown_content: str | None = None,
    ) -> str:
        source_markdown = markdown_text if markdown_text is not None else markdown_content
        if source_markdown is None:
            raise ValueError("markdown_text or markdown_content is required")

        body = self._markdown_to_html(source_markdown)
        body = self._strip_duplicate_title(body, title)
        sanitized = self._sanitize_html(body)
        return self._wrap_html(title=title, body_html=sanitized)

    def _markdown_to_html(self, markdown_text: str) -> str:
        if markdown is not None:
            return markdown.markdown(
                markdown_text,
                extensions=["extra", "sane_lists"],
            )

        lines = []
        for line in markdown_text.splitlines():
            if line.startswith("### "):
                lines.append(f"<h3>{escape(line[4:])}</h3>")
            elif line.startswith("## "):
                lines.append(f"<h2>{escape(line[3:])}</h2>")
            elif line.startswith("# "):
                lines.append(f"<h1>{escape(line[2:])}</h1>")
            elif line.startswith("- "):
                lines.append(f"<p>* {escape(line[2:])}</p>")
            elif line.startswith("> "):
                lines.append(f"<blockquote>{escape(line[2:])}</blockquote>")
            elif line.strip() == "---":
                lines.append("<hr />")
            elif line.strip():
                lines.append(f"<p>{escape(line)}</p>")
        return "\n".join(lines)

    def _sanitize_html(self, html_content: str) -> str:
        if BeautifulSoup is None:
            return html_content

        soup = BeautifulSoup(html_content, "html.parser")
        for bad_tag in soup(["script", "style", "iframe"]):
            bad_tag.decompose()
        return str(soup)

    def _strip_duplicate_title(self, html_content: str, title: str) -> str:
        if not title.strip():
            return html_content

        if BeautifulSoup is not None:
            soup = BeautifulSoup(html_content, "html.parser")
            first_heading = soup.find(["h1"])
            if first_heading and first_heading.get_text(" ", strip=True) == title.strip():
                first_heading.decompose()
            return str(soup)

        escaped_title = re.escape(title.strip())
        pattern = rf"^\s*<h1[^>]*>\s*{escaped_title}\s*</h1>\s*"
        return re.sub(pattern, "", html_content, count=1, flags=re.IGNORECASE)

    def _wrap_html(self, title: str, body_html: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{escape(title)}</title>
  </head>
  <body style="margin:0;padding:16px;background:#f7f7f7;">
    <section style="max-width:720px;margin:0 auto;background:#ffffff;padding:24px;border-radius:10px;">
      <h1 style="font-size:28px;line-height:1.4;color:#1f1f1f;margin:0 0 18px 0;">
        {escape(title)}
      </h1>
      <article style="font-size:16px;line-height:1.9;color:#2b2b2b;">
        {body_html}
      </article>
    </section>
  </body>
</html>
"""
