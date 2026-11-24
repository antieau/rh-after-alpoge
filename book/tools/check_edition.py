#!/usr/bin/env python3
"""Check the exported Gerby edition and record mechanical evidence (run by tools/build.py).

Fails on a statement page without its Lean links in the sidenote, a proof that is not attached,
a Lean link left inline in the text, or a broken anchor of the complete reader. Statements without
an introduction are reported, not failed, while the book is a draft.
"""
import json
import os
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = Path(os.environ.get("BOOK_SITE", ROOT / "site/book"))
EVIDENCE = ROOT / "runtime/evidence"


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.stack, self.inline_lean, self.contexts = [], [], [], [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if 'reading-context' in a.get('class', ''):
            self.contexts += 1
        inside = ((bool(self.stack and self.stack[-1][1]) or a.get('id') == 'tagContent')
                  and 'lean-sidenote' not in a.get('class', ''))
        if tag not in ['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta',
                       'param', 'source', 'track', 'wbr']:
            self.stack.append((tag, inside))
        if tag == 'a' and 'href' in a:
            self.links.append(a['href'])
            if inside and '/src/' in a['href']:
                self.inline_lean.append(a['href'])

    def handle_endtag(self, tag):
        at = next((i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i][0] == tag), None)
        if at is not None:
            self.stack = self.stack[:at]


def main():
    m = json.loads((EVIDENCE / 'statement-map.json').read_text())
    build = json.loads((ROOT / 'runtime/gerby/build/build-report.json').read_text())
    snap = json.loads((EVIDENCE / 'snapshot-report.json').read_text())
    failures, warnings, contexts, inline = [], [], 0, 0
    for item in m['items']:
        text = (SITE / 'tag' / (item['tag'] + '.html')).read_text()
        page = Page()
        page.feed(text)
        contexts += bool(page.contexts)
        inline += len(page.inline_lean)
        if not page.contexts:
            warnings.append('No statement introduction: ' + item['label'])
        for ref in item['lean_references']:
            # Tag pages are one level below the edition, which is one level below the site.
            url = ref['url'] if '://' in ref['url'] else '../../' + ref['url'].lstrip('/')
            if url not in page.links:
                failures.append('Missing source sidenote link: ' + item['label'] + ' ' + ref['requested_declaration'])
        if item['has_proof'] and not re.search(r'class="env-proof"', text):
            failures.append('Missing attached proof: ' + item['label'])
    page = Page()
    page.feed((SITE / 'read.html').read_text())
    ids = set(page.ids)
    missing = [x for x in page.links if x.startswith('#') and x[1:] not in ids]
    if missing:
        failures.append('Missing continuous-reader anchors: ' + str(missing[:10]))
    if inline:
        failures.append('Inline Lean links remain')
    if len(ids) != len(page.ids):
        failures.append('Duplicate reader IDs')
    presentation = {'tag_pages_checked': len(m['items']), 'introductions_on_individual_tags': contexts,
                    'all_Lean_witnesses_in_sidenotes': not inline, 'inline_Lean_links': inline,
                    'warnings': warnings, 'failures': failures}
    (EVIDENCE / 'presentation-report.json').write_text(json.dumps(presentation, indent=2) + '\n')
    integration = {'statement_pages_with_Lean_links': sum(bool(i['lean_references']) for i in m['items']),
                   'attached_proofs': build['proofs'], 'Gerby_dependencies': build['dependencies'],
                   'reader_local_anchors': len(ids), 'reader_missing_anchors': missing, 'failures': failures}
    (EVIDENCE / 'integration-report.json').write_text(json.dumps(integration, indent=2) + '\n')
    summary = {k: v for k, v in m.items() if k != 'items'}
    (EVIDENCE / 'preparation-report.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
    manifest = {'artifact': m['title'] + ': Gerby edition',
                'edition_status': 'Working draft; source-grounded prose, not a machine-certified decompilation.',
                'entry_points': {'tagged_edition': 'site/book/index.html', 'contents': 'site/book/contents.html',
                                 'complete_reader': 'site/book/read.html', 'source': 'runtime/build/resolution.tex',
                                 'pdf': json.loads((EVIDENCE / 'pdf-report.json').read_text())['pdf'],
                                 'bibliography': 'site/book/bibliography.html',
                                 'instructions': 'README.md'},
                'lean_archive_sha256': m['lean_archive_sha256'],
                'counts': {k: m[k] for k in ['labels', 'statements', 'statement_introductions', 'proofs',
                                             'unique_lean_references']},
                'chapters': len(json.loads((ROOT / 'manuscript/book.json').read_text())['entries']),
                'active_tags': build['active_tags'], 'html_pages': snap['html_pages'], 'files': snap['files'],
                'presentation': 'Native Gerby, Resolution branding, adapted LessWrong progress navigation',
                'limitations': ['Prose equivalence and mathematical completeness are not kernel-checked.',
                                'The Lean was not built for this edition.',
                                'HTML uses MathJax and public CDN assets; the PDF is self-contained.']}
    (EVIDENCE / 'edition-manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    shutil.copyfile(ROOT / 'runtime/build/gerby-build.log', EVIDENCE / 'gerby-build.log')
    print(json.dumps({'statements': len(m['items']), 'introductions': contexts, 'proofs': build['proofs'],
                      'Lean_references': m['unique_lean_references'], 'reader_anchors': len(ids),
                      'warnings': len(warnings), 'failures': failures}, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
