#!/usr/bin/env python3
"""Archive actual Gerby Flask responses as a portable, read-only HTML edition.

The edition goes to $BOOK_SITE (tools/build.py stages it beside site/book) with relative links,
so that it works under /book/ of the site. Links to /src/ (this site's Lean source pages) and to
/status (the status page) leave the edition for the site root, one level up.
"""
import html
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from gerby import app
from gerby.database import Tag, BibliographyEntry

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("BOOK_SITE", ROOT / "site/book"))
STATIC = ROOT / "runtime/deps/gerby-website/gerby/static"
DOWNLOADS = ROOT / "runtime/gerby/build/downloads"
OUTSIDE = {"/status": "../index.html", "/plan": "../plan.html"}


def outside(path):
    """The target, relative to the edition's root, of a link that leaves the edition."""
    if path in OUTSIDE:
        return OUTSIDE[path]
    if path.startswith("/src/"):
        return ".." + path
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(STATIC, OUT / "static", dirs_exist_ok=True)
    tags = list(sorted(Tag.select().where(Tag.active == True)))  # noqa: E712
    routes = {"/": "index.html", "/browse": "contents.html", "/about": "about.html",
              "/bibliography": "bibliography.html", "/statistics": "statistics.html",
              "/download/manuscript.tex": "resolution.tex", "/read": "read.html", "/search": "read.html"}
    # One page per tag. Workers deploys at most 20,000 files, and the Lean source pages take 8,000
    # of them, so each tag's citation and statistics pages are not exported; links to them become
    # plain text.
    for tag in tags:
        routes["/tag/" + tag.tag] = "tag/" + tag.tag + ".html"
        if tag.type in ['part', 'chapter', 'section', 'subsection']:
            routes['/read/' + tag.tag] = 'read/' + tag.tag + '.html'
    for entry in BibliographyEntry.select():
        routes['/bibliography/' + entry.key] = 'bibliography/' + entry.key + '.html'
    for path in DOWNLOADS.iterdir():
        routes['/download/' + path.name] = path.name

    def relative(target, current):
        return os.path.relpath(target, Path(current).parent).replace(os.sep, "/")

    def rewrite(text, current):
        # The archive has no HTTP application. Use the full-text reader in place
        # of the live SQLite search; the runnable Gerby instance retains search.
        text = re.sub(r'<form\b[^>]*\bid="quicksearch".*?</form>',
                      '<a href="' + relative("read.html", current)
                      + '">Find in text</a>', text, flags=re.S)

        def omit_unexported(m):
            parsed = urlsplit(html.unescape(m[2]))
            if (parsed.path.startswith("/") and not parsed.scheme and not parsed.netloc
                    and parsed.path not in routes and not parsed.path.startswith("/static/")
                    and not outside(parsed.path)):
                return "<span>" + m[4] + "</span>"
            return m[0]
        text = re.sub(r'<a\b([^>]*?)href="([^"]+)"([^>]*)>(.*?)</a>',
                      omit_unexported, text, flags=re.S)

        def attribute(m):
            attr, value = m.groups()
            parsed = urlsplit(html.unescape(value))
            if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
                return m[0]
            if parsed.path.startswith("/static/"):
                target = parsed.path.lstrip("/")
            elif parsed.path in routes:
                target = routes[parsed.path]
            elif outside(parsed.path):
                target = outside(parsed.path)
            else:
                return attr + '="#"'
            suffix = ("?" + parsed.query) if parsed.query and parsed.path.startswith("/static/") else ""
            suffix += ("#" + parsed.fragment) if parsed.fragment else ""
            return attr + '="' + html.escape(relative(target, current) + suffix) + '"'
        return re.sub(r'(href|src|action)="([^"]+)"', attribute, text)

    checks = []
    with app.test_client() as client:
        for route, filename in routes.items():
            if route == "/search":
                continue
            response = client.get(route)
            if response.status_code != 200:
                raise RuntimeError((route, response.status_code))
            dest = OUT / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not filename.endswith(".html"):
                dest.write_bytes(response.data)
            else:
                text = rewrite(response.get_data(as_text=True), filename)
                dest.write_text(text)
            checks.append({"route": route, "file": filename, "status": 200})

    # Workers serves no file over 25 MiB. Once the whole book no longer fits on one reader page, the
    # page is the table of contents, which leads to the reader of each chapter and section.
    if (OUT / "read.html").stat().st_size > 24 * 2**20:
        shutil.copyfile(OUT / "contents.html", OUT / "read.html")

    # Check every local file target, including downloads and the site's own pages beside the edition.
    missing = []
    for page in OUT.rglob("*.html"):
        for target in re.findall(r'(?:href|src)="([^"]+)"', page.read_text()):
            parsed = urlsplit(html.unescape(target))
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            if not (page.parent / parsed.path).exists():
                missing.append({"page": str(page.relative_to(OUT)), "target": target})
    if missing:
        raise RuntimeError("Missing exported file targets: " + repr(missing[:20]))
    report = {"method": "Actual Flask responses, including the native continuous-reader route",
              "routes": checks, "html_pages": len(list(OUT.rglob("*.html"))),
              "files": sum(1 for p in OUT.rglob("*") if p.is_file()),
              "missing_local_files": missing,
              "limitations": [
                  "The static snapshot uses browser Find in place of live SQLite search.",
                  "Live dependency graphs and comment/history services are not exported.",
                  "MathJax and upstream CSS/JavaScript CDN assets require an internet connection."
              ]}
    (ROOT / "runtime/evidence/snapshot-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "routes"}, indent=2))


if __name__ == "__main__":
    main()
