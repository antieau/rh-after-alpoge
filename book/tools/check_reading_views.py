#!/usr/bin/env python3
"""Check the merged chapter and section views, citations and PDF links (run by tools/build.py)."""
import json
import os
import re
import sqlite3
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = Path(os.environ.get("BOOK_SITE", ROOT / "site/book"))
EVIDENCE = ROOT / "runtime/evidence"


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids, self.hrefs = [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'a' and 'href' in a:
            self.hrefs.append(a['href'])


def main():
    failures = []
    db = sqlite3.connect(ROOT / 'runtime/gerby/build/resolution.sqlite')
    tags = db.execute('select tag,type,ref from tag where active=1').fetchall()
    statements = json.loads((EVIDENCE / 'statement-map.json').read_text())['items']
    labels = {i['tag'] for i in statements}
    views = []
    # A subsection shares its section's counter with the statements (Subsection 9.4.358 is followed by
    # Lemma 9.4.359), so its view holds the statements numbered after it and before the section's
    # next subsection.
    def position(ref):
        section, _, n = ref.rpartition('.')
        return section, int(n)
    starts = {}
    for t, k, r in tags:
        if k == 'subsection':
            section, n = position(r)
            starts.setdefault(section, []).append(n)
    subsections = {}
    for t, k, r in tags:
        if k == 'subsection':
            section, n = position(r)
            following = [m for m in starts[section] if m > n]
            subsections[t] = (section, n, min(following) if following else float('inf'))
    for tag, kind, ref in tags:
        if kind not in ['chapter', 'section', 'subsection']:
            continue
        text = (SITE / 'read' / (tag + '.html')).read_text()
        page = Page(text)
        if kind == 'subsection':
            section, start, end = subsections[tag]
            expected = {t for t, k, r in tags if t in labels and r.startswith(section + '.')
                        and r.count('.') == section.count('.') + 1 and start < position(r)[1] < end}
        else:
            expected = {t for t, k, r in tags if t in labels and r.startswith(ref + '.')}
        actual = set(re.findall(r'<article[^>]+id="([A-Z0-9]{4})"', text))
        if actual != expected:
            failures.append({'view': tag, 'missing': sorted(expected - actual), 'extra': sorted(actual - expected)})
        if len(page.ids) != len(set(page.ids)):
            failures.append('Duplicate IDs ' + tag)
        if any(h[1:] not in page.ids for h in page.hrefs if h.startswith('#')):
            failures.append('Missing local anchor ' + tag)
        views.append({'tag': tag, 'type': kind, 'statements': len(actual)})
    cite_pages = sorted((SITE / 'tag').glob('*-cite.html'))
    for p in cite_pages:
        if 'localhost' in p.read_text():
            failures.append('Localhost in citation: ' + p.name)
    chapters = len(json.loads((ROOT / 'manuscript/book.json').read_text())['entries'])
    chapter_links = re.findall(r'href="(chapter-[A-Z0-9]{4}-\d{8}-\d{4}Z\.pdf)"', (SITE / 'contents.html').read_text())
    if len(chapter_links) != chapters:
        failures.append('Expected ' + str(chapters) + ' chapter PDF links, found ' + str(len(chapter_links)))
    for p in SITE.glob('*.pdf'):
        if not p.read_bytes().startswith(b'%PDF'):
            failures.append('Invalid PDF ' + p.name)
    bibliography = len(list((SITE / 'bibliography').glob('*.html')))
    report = {'merged_views': views, 'merged_chapters': sum(x['type'] == 'chapter' for x in views),
              'merged_sections': sum(x['type'] == 'section' for x in views),
              'bibliography_entries': bibliography, 'chapter_pdf_links': len(chapter_links),
              'citation_pages_checked': len(cite_pages), 'failures': failures}
    (EVIDENCE / 'refinement-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'merged_views'}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
