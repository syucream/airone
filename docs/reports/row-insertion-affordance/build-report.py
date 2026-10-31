#!/usr/bin/env python3
"""Regenerates report.html from README.md, inlining every local image.

The report is published as a single self-contained file so it can be opened,
downloaded or previewed from a URL without any sibling files.
"""
import base64
import html
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent


def inline_image(match: re.Match) -> str:
    alt, src = match.group(1), match.group(2)
    path = (HERE / src).resolve()
    if not path.is_file():
        return f'<span class="missing">missing image: {html.escape(src)}</span>'
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<img alt="{html.escape(alt)}" src="data:image/png;base64,{data}">'


def inline(text: str) -> str:
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", inline_image, text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def convert(md: str) -> str:
    out, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(html.escape(lines[i]))
                i += 1
            i += 1
            out.append("<pre>" + "\n".join(block) + "</pre>")
            continue
        if m := re.match(r"^(#{1,4})\s+(.*)$", line):
            level = min(len(m.group(1)) + 1, 5)
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1]):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead><tbody>")
            for row in rows:
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>")
            out.append("</tbody></table>")
            continue
        if line.strip() == "---":
            out.append("<hr>")
            i += 1
            continue
        if line.startswith(">"):
            block = []
            while i < len(lines) and lines[i].startswith(">"):
                block.append(lines[i].lstrip("> ").strip())
                i += 1
            out.append("<blockquote>" + inline("<br>".join(block)) + "</blockquote>")
            continue
        if re.match(r"^[-*]\s+", line):
            block = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i]):
                block.append(lines[i][2:].strip())
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(b)}</li>" for b in block) + "</ul>")
            continue
        if re.match(r"^\d+\.\s+", line):
            block = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                block.append(re.sub(r"^\d+\.\s+", "", lines[i]))
                i += 1
            out.append("<ol>" + "".join(f"<li>{inline(b)}</li>" for b in block) + "</ol>")
            continue
        if line.strip() == "":
            i += 1
            continue
        out.append(f"<p>{inline(line)}</p>")
        i += 1
    return "\n".join(out)


body = convert((HERE / "README.md").read_text(encoding="utf-8"))
doc = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>行追加UIの改善 — スクリーンショット付き検証レポート</title>
<style>
  body {{ margin: 0; padding: 0 0 64px; font-family: "Hiragino Sans","Noto Sans JP",system-ui,sans-serif;
         color: #212b33; background: #f4f6f8; line-height: 1.7; }}
  main {{ max-width: 1180px; margin: 0 auto; padding: 24px; background: #fff;
          border: 1px solid #dde3e8; border-radius: 8px; }}
  h1 {{ font-size: 24px; margin: 0 0 12px; padding-bottom: 10px; border-bottom: 3px solid #1976d2; }}
  h2 {{ font-size: 19px; margin: 32px 0 10px; padding-bottom: 6px; border-bottom: 2px solid #e3e8ec; }}
  h3 {{ font-size: 15px; margin: 24px 0 8px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin: 10px 0 18px; }}
  th, td {{ border: 1px solid #e0e6ea; padding: 8px 10px; vertical-align: top; }}
  th {{ background: #eceff1; text-align: left; }}
  img {{ max-width: 100%; border: 1px solid #dde3e8; border-radius: 4px; background: #fff; display: block; }}
  pre {{ background: #17222b; color: #d7e3ea; padding: 12px 14px; border-radius: 6px;
         overflow-x: auto; font-size: 12px; }}
  code {{ background: #eef1f4; padding: 1px 4px; border-radius: 3px; font-size: 92%; }}
  pre code {{ background: none; padding: 0; }}
  blockquote {{ margin: 12px 0; padding: 10px 14px; border-left: 4px solid #1976d2;
                background: #eef4fa; font-size: 13px; }}
  hr {{ border: 0; border-top: 1px solid #e3e8ec; margin: 28px 0; }}
  .missing {{ color: #c62828; font-weight: 700; }}
</style>
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""
(HERE / "report.html").write_text(doc, encoding="utf-8")
print(f"wrote report.html ({(HERE / 'report.html').stat().st_size / 1024:.0f} KiB)")
