#!/usr/bin/env python3
"""Render the paper markdown into a formal single-column HTML/PDF layout."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import re
import shutil
import subprocess
import sys

try:
    import markdown  # type: ignore
except ImportError as exc:  # pragma: no cover - runtime guidance
    raise SystemExit(
        "Missing dependency: python package 'markdown'. "
        "Install it with: python3 -m pip install markdown"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKDOWN = ROOT / "docs" / "behavior-constrained-agent-systems-paper.md"
DEFAULT_HTML = ROOT / "docs" / "behavior-constrained-agent-systems-paper.html"
DEFAULT_PDF = ROOT / "paper" / "behavior-constrained-agent-systems-paper.pdf"


def format_today() -> str:
    today = date.today()
    return f"{today.strftime('%B')} {today.day}, {today.year}"


def extract_front_matter(markdown_text: str) -> tuple[str, str, str, str]:
    lines = markdown_text.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError("Expected the first line to be a level-1 markdown title")

    title = lines[0][2:].strip()
    author = ""
    email = ""
    body_start = 1

    for index in range(1, min(len(lines), 8)):
        line = lines[index].strip()
        if not line:
            continue
        if line.startswith("**") and line.endswith("**") and not author:
            author = line.strip("*")
            body_start = index + 1
            continue
        if line.startswith("`") and line.endswith("`") and not email:
            email = line.strip("`")
            body_start = index + 1
            continue
        break

    body = "\n".join(lines[body_start:]).lstrip()
    return title, author, email, body


def build_body_html(markdown_body: str) -> str:
    html = markdown.markdown(
        markdown_body,
        extensions=["fenced_code", "tables", "sane_lists"],
    )

    abstract_match = re.search(
        r"<h2>Abstract</h2>(?P<content>.*?)(?=<h2>1\. Introduction</h2>)",
        html,
        flags=re.S,
    )
    if abstract_match:
        abstract_content = abstract_match.group("content").strip()
        abstract_content = abstract_content.replace(
            "<p><strong>Keywords:</strong>",
            '<p class="keywords"><span class="keywords-label">Keywords:</span>',
        )
        abstract_block = (
            '<section class="abstract-block">'
            '<div class="abstract-heading">Abstract</div>'
            f"{abstract_content}"
            "</section>"
        )
        html = (
            html[: abstract_match.start()]
            + abstract_block
            + html[abstract_match.end() :]
        )

    references_match = re.search(
        r"<h2>References</h2>(?P<content>.*)$",
        html,
        flags=re.S,
    )
    if references_match:
        ref_content = references_match.group("content")
        entries = re.findall(r"<p>(.*?)</p>", ref_content, flags=re.S)
        rendered_entries = "\n".join(
            f'<div class="reference-item">{entry}</div>' for entry in entries
        )
        references_block = (
            '<section class="references-block">'
            "<h2>References</h2>"
            f"{rendered_entries}"
            "</section>"
        )
        html = (
            html[: references_match.start()]
            + references_block
            + html[references_match.end() :]
        )

    return html


def build_html_document(title: str, author: str, email: str, body_html: str) -> str:
    meta_line = format_today()
    css = """
    @page {
      size: A4;
      margin: 16mm 16mm 18mm 16mm;
    }

    body {
      margin: 0;
      color: #111;
      background: #fff;
      font-family: Georgia, "Times New Roman", serif;
      line-height: 1.48;
      -webkit-font-smoothing: antialiased;
    }

    .paper {
      max-width: 760px;
      margin: 0 auto;
      padding: 16mm 8mm 18mm;
      box-sizing: border-box;
    }

    .paper-header {
      margin-bottom: 12px;
      text-align: center;
    }

    .paper-title {
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 21pt;
      line-height: 1.16;
      font-weight: 700;
      letter-spacing: -0.02em;
      margin: 0 0 8px;
      color: #000;
    }

    .paper-author {
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 11.5pt;
      font-weight: 600;
      margin: 0;
      text-align: center;
    }

    .paper-email {
      font-family: Georgia, "Times New Roman", serif;
      font-size: 9.8pt;
      margin: 2px 0 6px;
      color: #444;
      text-align: center;
    }

    .paper-meta {
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 8pt;
      letter-spacing: 0.03em;
      color: #8a8a8a;
      padding-top: 0;
      display: block;
      border-top: 0;
      text-align: center;
    }

    .abstract-block {
      margin: 10px 0 18px;
      padding: 8px 0 6px;
      border-top: 1px solid #3a3a3a;
      border-bottom: 1px solid #bdbdbd;
      background: transparent;
      break-inside: avoid;
    }

    .abstract-heading {
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 8.4pt;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: #333;
      margin-bottom: 6px;
    }

    .abstract-block p:first-of-type {
      margin-top: 0;
    }

    .keywords {
      font-size: 9.4pt;
      color: #333;
      margin-top: 6px;
    }

    .keywords-label {
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 8.2pt;
      margin-right: 6px;
    }

    h2, h3 {
      color: #000;
      break-after: avoid-page;
    }

    h2 {
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 14pt;
      font-weight: 700;
      margin: 18px 0 8px;
      padding: 0;
      border: 0;
      letter-spacing: -0.01em;
    }

    h3 {
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      font-size: 11pt;
      font-weight: 700;
      margin: 14px 0 7px;
    }

    p, li {
      font-size: 11pt;
    }

    p {
      margin: 0 0 0.62em;
      text-align: justify;
      text-justify: inter-word;
    }

    ul, ol {
      margin: 0.35em 0 0.8em 1.2em;
      padding-left: 1.1em;
    }

    li {
      margin: 0.18em 0;
    }

    code {
      font-family: Menlo, Monaco, "Courier New", monospace;
      font-size: 0.92em;
      background: #f3f3f3;
      border: 1px solid #e2e2e2;
      border-radius: 3px;
      padding: 0.05em 0.28em;
    }

    pre {
      background: #f9f9f9;
      border: 1px solid #e3e3e3;
      border-radius: 4px;
      padding: 10px 12px;
      overflow: visible;
      margin: 0.8em 0 1em;
      break-inside: avoid-page;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      word-break: break-word;
    }

    pre code {
      background: transparent;
      border: 0;
      border-radius: 0;
      padding: 0;
      font-size: 9.4pt;
      line-height: 1.4;
      white-space: inherit;
    }

    blockquote {
      margin: 0.8em 0 0.9em;
      padding-left: 14px;
      border-left: 2px solid #c9c9c9;
      color: #444;
    }

    a {
      color: #1a4e8a;
      text-decoration: none;
    }

    .references-block h2 {
      margin-bottom: 12px;
    }

    .references-block {
      background: transparent;
    }

    .reference-item {
      font-size: 10.6pt;
      line-height: 1.42;
      padding-left: 1.8em;
      text-indent: -1.8em;
      margin: 0 0 0.65em;
    }

    .reference-item code {
      font-size: 0.88em;
    }
    """

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>{css}</style>
  </head>
  <body>
    <main class="paper">
      <header class="paper-header">
        <h1 class="paper-title">{title}</h1>
        <p class="paper-author">{author}</p>
        <p class="paper-email">{email}</p>
        <div class="paper-meta">{meta_line}</div>
      </header>
      {body_html}
    </main>
  </body>
</html>
"""


def find_chrome_binary() -> str | None:
    candidates = [
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def render_pdf(html_path: Path, pdf_path: Path) -> None:
    chrome = find_chrome_binary()
    if chrome is None:
        raise SystemExit(
            "Could not find a Chrome/Chromium binary for PDF export. "
            "Generated the HTML successfully, but PDF export was skipped."
        )

    subprocess.run(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--print-to-pdf={pdf_path}",
            "--no-pdf-header-footer",
            html_path.resolve().as_uri(),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--html-out", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--pdf-out", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--html-only", action="store_true")
    args = parser.parse_args()

    markdown_text = args.source.read_text(encoding="utf-8")
    title, author, email, body = extract_front_matter(markdown_text)
    body_html = build_body_html(body)
    html_document = build_html_document(title, author, email, body_html)

    args.html_out.parent.mkdir(parents=True, exist_ok=True)
    args.html_out.write_text(html_document, encoding="utf-8")
    print(f"wrote HTML to {args.html_out}")

    if not args.html_only:
        args.pdf_out.parent.mkdir(parents=True, exist_ok=True)
        render_pdf(args.html_out, args.pdf_out)
        print(f"wrote PDF to {args.pdf_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
