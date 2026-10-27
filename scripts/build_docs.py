"""把 Markdown 技术文档与安全自评报告渲染成 PDF（供竞赛提交）。

没有 pandoc 也能用：自己把 Markdown 转成带打印样式的一次性 HTML，
再交给本机 Edge 的 --print-to-pdf。只用标准库。

用法：python scripts/build_docs.py
产出：deliverables/01_技术文档.pdf
      deliverables/04_安全自评报告.pdf
"""
from __future__ import annotations

import html
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDGE = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")

PRINT_CSS = """
@page { size: A4; margin: 17mm 15mm 17mm 15mm; }
* { box-sizing: border-box; }
body {
  font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
  font-size: 10.5pt; line-height: 1.72; color: #1a1f29; margin: 0;
}
h1 { font-size: 19pt; color: #123f86; margin: 0 0 10pt; }
h2 { font-size: 14.5pt; color: #123f86; margin: 16pt 0 6pt;
     padding-bottom: 3pt; border-bottom: 1.5pt solid #dbe4f0; page-break-after: avoid; }
h3 { font-size: 12pt; color: #1f5fbf; margin: 11pt 0 5pt; page-break-after: avoid; }
h4 { font-size: 10.8pt; margin: 9pt 0 4pt; page-break-after: avoid; }
p { margin: 5pt 0; text-align: justify; }
ul, ol { margin: 5pt 0 5pt 16pt; padding-left: 8pt; }
li { margin: 2.5pt 0; }
strong { color: #0f2b5c; }
code {
  font-family: Consolas, "Cascadia Mono", monospace; font-size: 8.8pt;
  background: #f1f4f9; padding: 1pt 3pt; border-radius: 2pt; color: #223;
}
pre {
  background: #f6f8fb; border: 0.6pt solid #dde4ee; border-radius: 3pt;
  padding: 7pt 9pt; margin: 7pt 0; white-space: pre-wrap; word-break: break-word;
  font-size: 8.4pt; line-height: 1.5; page-break-inside: avoid;
}
pre code { background: none; padding: 0; font-size: inherit; }
table {
  width: 100%; border-collapse: collapse; margin: 7pt 0; font-size: 8.8pt;
  page-break-inside: auto;
}
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
th, td { border: 0.6pt solid #c9d3e0; padding: 4pt 6pt; text-align: left; vertical-align: top; }
th:first-child, td:first-child { min-width: 40pt; }
th { background: #eef3fa; color: #123f86; font-weight: 700; }
blockquote {
  margin: 7pt 0; padding: 6pt 10pt; border-left: 2.5pt solid #1f5fbf;
  background: #f4f8fd; color: #33415a;
}
blockquote p { margin: 2pt 0; }
hr { border: none; border-top: 0.8pt solid #dbe4f0; margin: 12pt 0; }
img { max-width: 100%; display: block; margin: 8pt auto; page-break-inside: avoid; }
a { color: #1f5fbf; text-decoration: none; word-break: break-all; }

/* 封面 */
.cover { height: 252mm; display: flex; flex-direction: column; justify-content: center;
         page-break-after: always; text-align: center; }
.cover .kicker { font-size: 10pt; letter-spacing: 3pt; color: #7c8aa0; }
.cover h1 { font-size: 27pt; margin: 12pt 0 8pt; letter-spacing: 1pt; }
.cover .sub { font-size: 12pt; color: #33415a; }
.cover .rule { width: 60mm; height: 2.5pt; background: #1f5fbf; margin: 16pt auto; }
.cover .meta { margin-top: 36pt; font-size: 10pt; color: #4a5a70; line-height: 2.1; }

/* 目录 */
.toc { page-break-after: always; }
.toc h2 { border: none; }
.toc div { font-size: 10pt; margin: 3pt 0; color: #33415a; }
.toc .lv2 { padding-left: 0; font-weight: 600; color: #123f86; margin-top: 7pt; }
.toc .lv3 { padding-left: 14pt; }
"""


def inline(text: str, base: Path) -> str:
    """行内元素：图片、链接、加粗、行内代码。"""
    text = html.escape(text)

    def image(match):
        alt, src = match.group(1), match.group(2)
        path = (base / src).resolve()
        return f'<img src="{path.as_uri()}" alt="{alt}">'

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", image, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def split_row(line: str) -> list[str]:
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def md_to_html(md: str, base: Path, cover: dict) -> str:
    body: list[str] = []
    lines = md.splitlines()
    index = 0
    paragraph: list[str] = []
    list_tag: str | None = None
    toc: list[tuple[int, str, str]] = []

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            body.append("<p>" + "<br>".join(inline(l, base) for l in paragraph) + "</p>")
            paragraph = []

    def close_list():
        nonlocal list_tag
        if list_tag:
            body.append(f"</{list_tag}>")
            list_tag = None

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph(); close_list()
            code: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            body.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and \
                re.match(r"^\|[\s:\-|]+\|$", lines[index + 1].strip()):
            flush_paragraph(); close_list()
            header = split_row(lines[index])
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(split_row(lines[index]))
                index += 1
            table = ["<table><thead><tr>"]
            table += [f"<th>{inline(c, base)}</th>" for c in header]
            table.append("</tr></thead><tbody>")
            for row in rows:
                table.append("<tr>" + "".join(f"<td>{inline(c, base)}</td>"
                                              for c in row) + "</tr>")
            table.append("</tbody></table>")
            body.append("".join(table))
            continue

        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            flush_paragraph(); close_list()
            level = len(heading.group(1))
            title = heading.group(2)
            anchor = f"h-{len(toc)}"
            toc.append((level, title, anchor))
            body.append(f'<h{level} id="{anchor}">{inline(title, base)}</h{level}>')
            index += 1
            continue

        if stripped == "---":
            flush_paragraph(); close_list()
            body.append("<hr>")
            index += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph(); close_list()
            quote: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip().lstrip(">").strip())
                index += 1
            body.append("<blockquote>" + "".join(
                f"<p>{inline(q, base)}</p>" for q in quote if q) + "</blockquote>")
            continue

        unordered = re.match(r"^[-*]\s+(.*)$", stripped)
        ordered = re.match(r"^\d+\.\s+(.*)$", stripped)
        if unordered or ordered:
            flush_paragraph()
            wanted = "ul" if unordered else "ol"
            if list_tag != wanted:
                close_list()
                body.append(f"<{wanted}>")
                list_tag = wanted
            body.append(f"<li>{inline((unordered or ordered).group(1), base)}</li>")
            index += 1
            continue

        if not stripped:
            flush_paragraph(); close_list()
            index += 1
            continue

        close_list()
        paragraph.append(stripped)
        index += 1

    flush_paragraph(); close_list()

    # 封面 + 目录
    cover_html = (
        '<div class="cover">'
        f'<div class="kicker">{html.escape(cover["kicker"])}</div>'
        f'<h1>{html.escape(cover["title"])}</h1>'
        f'<div class="sub">{html.escape(cover["sub"])}</div>'
        '<div class="rule"></div>'
        f'<div class="meta">{cover["meta"]}</div>'
        "</div>"
    )
    toc_html = ['<div class="toc"><h2>目　录</h2>']
    for level, title, anchor in toc:
        if level <= 1:
            continue
        css = "lv2" if level == 2 else "lv3"
        toc_html.append(f'<div class="{css}">{html.escape(title)}</div>')
    toc_html.append("</div>")

    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        f"<style>{PRINT_CSS}</style></head><body>"
        + cover_html + "".join(toc_html) + "".join(body)
        + "</body></html>"
    )


def build(md_path: Path, out_pdf: Path, cover: dict) -> Path:
    document = md_to_html(md_path.read_text(encoding="utf-8"), md_path.parent, cover)
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "doc.html"
        html_path.write_text(document, encoding="utf-8")
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            str(EDGE), "--headless=new", "--disable-gpu", "--no-sandbox",
            "--no-first-run", "--print-to-pdf-no-header",
            f"--user-data-dir={Path(tmp) / 'profile'}",
            f"--print-to-pdf={out_pdf}", html_path.as_uri(),
        ], check=True, capture_output=True, timeout=180)
    return out_pdf


JOBS = [
    {
        "md": ROOT / "docs" / "技术方案.md",
        "pdf": ROOT / "deliverables" / "01_技术文档.pdf",
        "cover": {
            "kicker": "国际金融科技大赛 · 技术文档",
            "title": "银龄暖声",
            "sub": "面向老年人的语音数字银行管家",
            "meta": "系统架构图 · 核心算法说明 · 安全设计<br>"
                    "仓库：elder-voice-bank-agent<br>2026 年 10 月",
        },
    },
    {
        "md": ROOT / "docs" / "安全自评报告.md",
        "pdf": ROOT / "deliverables" / "04_安全自评报告.pdf",
        "cover": {
            "kicker": "国际金融科技大赛 · 安全自评报告",
            "title": "银龄暖声 · 安全自评",
            "sub": "权限分级实现说明与已知风险清单",
            "meta": "评估环境：自建模拟银行沙箱<br>"
                    "仓库：elder-voice-bank-agent<br>2026 年 10 月",
        },
    },
]


if __name__ == "__main__":
    for job in JOBS:
        pdf = build(job["md"], job["pdf"], job["cover"])
        print(f"已生成 {pdf.name}（{pdf.stat().st_size / 1024 / 1024:.2f} MB）")
