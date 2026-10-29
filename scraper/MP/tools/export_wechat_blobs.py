#!/usr/bin/env python3
"""Export cached WeChat article HTML blobs to a local archive.

This reads Chromium IndexedDB blob files produced by down.mptext.top and writes
raw HTML, lightweight Markdown, and an index. It does not read cookies or any
browser credential stores.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


TARGET_FAKEID = "Mzg4ODY1NTUwOQ=="


def safe_name(value: str, fallback: str = "article") -> str:
    value = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", value).strip()
    value = re.sub(r"\s+", " ", value)
    return (value[:90] or fallback).rstrip(". ")


def first_match(patterns: Iterable[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.S)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def parse_publish_time(raw_html: str) -> tuple[int | None, str]:
    value = first_match(
        [
            r"var\s+ct\s*=\s*['\"]?(\d{9,10})['\"]?",
            r"oriCreateTime\s*=\s*['\"]?(\d{9,10})['\"]?",
            r"oriCreateTime:\s*['\"]?(\d{9,10})['\"]?",
        ],
        raw_html,
    )
    if not value:
        return None, ""
    timestamp = int(value)
    return timestamp, dt.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


class InnerHtmlExtractor(HTMLParser):
    def __init__(self, target_id: str):
        super().__init__(convert_charrefs=False)
        self.target_id = target_id
        self.collecting = False
        self.depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if not self.collecting and attrs_dict.get("id") == self.target_id:
            self.collecting = True
            self.depth = 1
            return
        if self.collecting:
            self.parts.append(self.get_starttag_text() or "")
            if tag.lower() not in {"br", "img", "meta", "link", "input", "hr"}:
                self.depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.collecting:
            self.parts.append(self.get_starttag_text() or "")

    def handle_endtag(self, tag: str) -> None:
        if not self.collecting:
            return
        self.depth -= 1
        if self.depth <= 0:
            self.collecting = False
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self.collecting:
            self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if self.collecting:
            self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if self.collecting:
            self.parts.append(f"&#{name};")

    def get_html(self) -> str:
        return "".join(self.parts)


class MarkdownConverter(HTMLParser):
    block_tags = {
        "article",
        "blockquote",
        "div",
        "figure",
        "figcaption",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "p",
        "section",
        "table",
        "tr",
        "ul",
        "ol",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.link_stack: list[str] = []

    def text(self, value: str) -> None:
        if self.skip_depth:
            return
        value = re.sub(r"\s+", " ", value)
        if value:
            self.parts.append(value)

    def newline(self, count: int = 1) -> None:
        if self.skip_depth:
            return
        current = "".join(self.parts)
        needed = "\n" * count
        if not current.endswith(needed):
            self.parts.append(needed)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = dict(attrs)
        if tag in {"script", "style", "svg"}:
            self.skip_depth += 1
            return
        if tag in self.block_tags:
            self.newline(2 if tag.startswith("h") else 1)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("#" * int(tag[1]) + " ")
        elif tag == "br":
            self.newline(1)
        elif tag == "a":
            self.link_stack.append(attrs_dict.get("href") or "")
        elif tag == "img":
            src = attrs_dict.get("data-src") or attrs_dict.get("src") or ""
            alt = attrs_dict.get("alt") or ""
            if src:
                self.newline(1)
                self.parts.append(f"![{alt}]({html.unescape(src)})")
                self.newline(1)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip_depth:
            if tag in {"script", "style", "svg"}:
                self.skip_depth -= 1
            return
        if tag == "a":
            href = self.link_stack.pop() if self.link_stack else ""
            if href:
                self.parts.append(f" ({html.unescape(href)})")
        if tag in self.block_tags:
            self.newline(2 if tag.startswith("h") else 1)

    def handle_data(self, data: str) -> None:
        self.text(data)

    def markdown(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"


def article_content_html(raw_html: str) -> str:
    parser = InnerHtmlExtractor("js_content")
    parser.feed(raw_html)
    return parser.get_html()


def html_to_markdown(content_html: str) -> str:
    parser = MarkdownConverter()
    parser.feed(content_html)
    return parser.markdown()


def parse_article(path: Path) -> dict | None:
    raw_html = path.read_text(errors="ignore")
    if "mp.weixin.qq.com" not in raw_html or "id=\"js_content\"" not in raw_html:
        return None
    fakeid = first_match([r'biz:\s*"([^"]+)"', r'var\s+__biz\s*=\s*"([^"]+)"'], raw_html)
    if fakeid != TARGET_FAKEID:
        return None
    title = first_match(
        [
            r"var\s+msg_title\s*=\s*'(.+?)'\.html\(false\)",
            r'<h1[^>]*id="activity-name"[^>]*>(.*?)</h1>',
        ],
        raw_html,
    )
    url = first_match([r'var\s+msg_link\s*=\s*"([^"]+)"'], raw_html)
    mid = first_match([r'mid:\s*"([^"]+)"', r'appmsgid\s*=\s*"([^"]+)"'], raw_html)
    idx = first_match([r'idx:\s*"([^"]+)"', r'itemidx\s*=\s*"([^"]+)"'], raw_html)
    author = first_match([r'var\s+author\s*=\s*"([^"]*)"', r'nickname\s*=\s*"([^"]*)"'], raw_html)
    digest = first_match([r'var\s+msg_desc\s*=\s*htmlDecode\("([^"]*)"\)'], raw_html)
    cover = first_match([r'var\s+msg_cdn_url\s*=\s*"([^"]*)"'], raw_html)
    timestamp, publish_time = parse_publish_time(raw_html)
    content_html = article_content_html(raw_html)
    markdown = html_to_markdown(content_html)
    return {
        "blob_path": str(path),
        "fakeid": fakeid,
        "mid": mid,
        "idx": idx,
        "aid": f"{mid}_{idx}" if mid and idx else "",
        "title": title,
        "url": url,
        "author": author,
        "digest": digest,
        "cover_url": cover,
        "publish_timestamp": timestamp,
        "publish_time": publish_time,
        "raw_html": raw_html,
        "content_html": content_html,
        "markdown": markdown,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blob-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    articles = []
    for path in args.blob_dir.iterdir():
        if path.is_file():
            article = parse_article(path)
            if article:
                articles.append(article)

    articles.sort(
        key=lambda item: (
            item["publish_timestamp"] or 0,
            int(item["mid"] or 0),
            -int(item["idx"] or 0),
        ),
        reverse=True,
    )
    articles = articles[: args.limit]

    raw_dir = args.output_dir / "raw-html"
    md_dir = args.output_dir / "markdown"
    raw_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)

    index_rows = []
    manifest = []
    for seq, article in enumerate(articles, 1):
        date_prefix = (article["publish_time"][:10] or "unknown").replace("-", "")
        name = f"{seq:03d}-{date_prefix}-{safe_name(article['title'])}"
        html_path = raw_dir / f"{name}.html"
        md_path = md_dir / f"{name}.md"
        html_path.write_text(article["raw_html"], encoding="utf-8")
        frontmatter = {
            "title": article["title"],
            "account_name": "谷雨星球",
            "fakeid": article["fakeid"],
            "source_url": article["url"],
            "publish_time": article["publish_time"],
            "aid": article["aid"],
            "author": article["author"],
            "cover_url": article["cover_url"],
        }
        md_text = "---\n" + json.dumps(frontmatter, ensure_ascii=False, indent=2) + "\n---\n\n"
        md_text += f"# {article['title']}\n\n"
        md_text += f"- 公众号: 谷雨星球\n- 发布时间: {article['publish_time']}\n- 原文: {article['url']}\n\n"
        md_text += article["markdown"]
        md_path.write_text(md_text, encoding="utf-8")
        row = {
            "seq": seq,
            "title": article["title"],
            "source_url": article["url"],
            "publish_time": article["publish_time"],
            "aid": article["aid"],
            "author": article["author"],
            "digest": article["digest"],
            "cover_url": article["cover_url"],
            "markdown_path": str(md_path),
            "html_path": str(html_path),
            "blob_path": article["blob_path"],
        }
        index_rows.append(row)
        manifest.append(row)

    index_path = args.output_dir / "index.csv"
    with index_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(index_rows[0].keys()) if index_rows else [])
        writer.writeheader()
        writer.writerows(index_rows)

    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "account_name": "谷雨星球",
        "fakeid": TARGET_FAKEID,
        "article_count": len(articles),
        "first_publish_time": articles[-1]["publish_time"] if articles else "",
        "last_publish_time": articles[0]["publish_time"] if articles else "",
        "output_dir": str(args.output_dir),
        "markdown_dir": str(md_dir),
        "raw_html_dir": str(raw_dir),
        "index_csv": str(index_path),
        "manifest_json": str(manifest_path),
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
