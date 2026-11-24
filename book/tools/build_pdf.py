#!/usr/bin/env python3
"""Typeset the Gerby manuscript and extract navigable chapter PDFs (run by tools/build.py).

The PDFs carry their UTC build time in their names: rh-after-alpoge-<YYYYMMDD-HHMM>Z.pdf for the
book and chapter-<TAG>-<YYYYMMDD-HHMM>Z.pdf for the chapters. They go to runtime/gerby/build/downloads/
(which holds only the current build's), and runtime/gerby/build/pdf.json records their names for the
Gerby templates (gerby/configuration.py). The title page gives the build time and the commit, with a
note when the book's working tree differs from it.

Lean links in the PDF point where the web edition's do: the archive's files in the book's public
repository (tools/lean_source.py).
TeX errors, undefined references and missing characters fail the build; overfull boxes are
counted in runtime/evidence/pdf-report.json but do not fail it while the book is a draft.
"""
import argparse
import functools
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
BUILD = RUNTIME / "build"
EVIDENCE = RUNTIME / "evidence"
DOWNLOADS = RUNTIME / "gerby/build/downloads"
NAMES = RUNTIME / "gerby/build/pdf.json"
BOOK_STEM = "rh-after-alpoge"
SITE = "https://rh.antieau.workers.dev"
TITLE = json.loads((ROOT / "manuscript/book.json").read_text())["title"]
PREAMBLE = r'''\documentclass[11pt,a4paper,oneside]{report}
\usepackage[left=27mm,right=30mm,top=25mm,bottom=26mm,marginparwidth=17mm,marginparsep=5mm]{geometry}
\usepackage{amssymb,amsmath,amsthm,lmodern,microtype,xcolor,xurl,hyperref,fancyhdr,newunicodechar}
\definecolor{slate}{HTML}{435A78}
\hypersetup{colorlinks=true,linkcolor=slate,citecolor=slate,urlcolor=slate,bookmarksnumbered=true,pdftitle={@TITLE@},pdfauthor={Benjamin Antieau}}
% Latin Modern has no Cyrillic. The Tate-Shafarevich group's letter comes from the AMS
% Washington Cyrillic font, as in the usual \Sha; it works in text and in \text{...}.
\DeclareFontFamily{U}{wncy}{}
\DeclareFontShape{U}{wncy}{m}{n}{<->wncyr10}{}
\newunicodechar{Ш}{\textnormal{\usefont{U}{wncy}{m}{n}\char"58}}
\theoremstyle{plain}
\newtheorem{theorem}[subsection]{Theorem}
\newtheorem{proposition}[subsection]{Proposition}
\newtheorem{lemma}[subsection]{Lemma}
\newtheorem{corollary}[subsection]{Corollary}
\newtheorem{conjecture}[subsection]{Conjecture}
\theoremstyle{definition}
\newtheorem{definition}[subsection]{Definition}
\newtheorem{situation}[subsection]{Situation}
\newtheorem{example}[subsection]{Example}
\newtheorem{notation}[subsection]{Notation}
\theoremstyle{remark}
\newtheorem{remark}[subsection]{Remark}
% Set the tag before amsthm constructs its heading. The zero-width overlay
% shares the heading's baseline and page, instead of floating as a marginpar.
\newcommand{\statementtag}{}
\makeatletter
\let\resolution@thmhead\thmhead
\renewcommand{\thmhead}[3]{%
  \rlap{\hspace*{\dimexpr\linewidth+\marginparsep\relax}%
    {\normalfont\scriptsize\ttfamily\color{slate}\statementtag}}%
  \resolution@thmhead{#1}{#2}{#3}}
\makeatother
\setlength{\parskip}{.25em}
\setlength{\emergencystretch}{2em}
\setlength{\headheight}{14pt}
\pagestyle{fancy}\fancyhf{}\fancyhead[L]{\small\nouppercase{\leftmark}}\fancyfoot[C]{\thepage}
\renewcommand{\chaptermark}[1]{\markboth{\thechapter.\ #1}{}}
\renewcommand{\headrulewidth}{0pt}
\begin{document}
\hypersetup{pageanchor=false}
\begin{titlepage}
\vspace*{50mm}
{\Huge The Riemann Hypothesis\par}
\vspace{6mm}
{\Huge after Alpöge\par}
\vspace{16mm}
{\large A reading of Levent Alpöge's Lean proof of the Riemann Hypothesis\par}
\vspace{2mm}
{\large and of the Generalized Riemann Hypothesis for Dirichlet $L$-functions\par}
\vfill
{\small A working draft, not Alpöge's own exposition.\par}
\vspace{2mm}
{\small @BUILT@\par}
\vspace{2mm}
{\small Lean archive SHA-256 \texttt{@SHA@}\par}
\vspace{8mm}
{\small Created by Benjamin Antieau at Resolution.\par}
\end{titlepage}
\pagenumbering{roman}\hypersetup{pageanchor=true}
\tableofcontents
\clearpage\pagenumbering{arabic}
'''
HEADINGS = "theorem|proposition|lemma|corollary|definition|situation|example|remark|conjecture|notation"
OPTIONAL = r"(?:\[(?:[^\[\]]|\[[^\]]*\])*\])?"


def tex_environment():
    """TEX_LD_LIBRARY_PATH, if set, is the library path for TeX alone (for a TeX Live whose
    fontconfig and freetype are not installed system-wide)."""
    env = dict(os.environ)
    if env.get('TEX_LD_LIBRARY_PATH'):
        env['LD_LIBRARY_PATH'] = env['TEX_LD_LIBRARY_PATH']
    return env


def revision():
    """The short hash of HEAD, and whether the book's working tree differs from it (None, None
    outside Git)."""
    def git(*args):
        return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True)
    head = git('rev-parse', '--short', 'HEAD')
    if head.returncode:
        return None, None
    if os.environ.get('BOOK_MANUSCRIPT'):
        return head.stdout.strip(), False
    return head.stdout.strip(), bool(git('status', '--porcelain', '--', '.').stdout.strip())


def build_line(built, commit, dirty):
    """The title page's line on the build, e.g. Built 2026-11-21 01:45 UTC from commit abc1234."""
    line = 'Built ' + built.strftime('%Y-%m-%d %H:%M') + ' UTC'
    if commit:
        line += r' from commit \texttt{' + commit + '}' + (', with uncommitted changes' if dirty else '')
    return line + '.'


def lean_url(link):
    """A Lean link of the prepared manuscript, percent-encoded and escaped for \\href (a link to
    this site, /src/..., is made absolute)."""
    path, _, line = link.partition("#")
    return (("" if "://" in path else SITE) + quote(path, safe="/:") + "#" + line).replace("%", r"\%")


def bibliography_tex():
    code = """import json,sys
from pybtex.database import parse_file
bib=parse_file(sys.argv[1])
print(json.dumps([{'key':k,'fields':dict(v.fields),'authors':[' '.join(p.first_names+p.middle_names+p.prelast_names+p.last_names+p.lineage_names) for p in v.persons.get('author',[])]} for k,v in bib.entries.items()]))
"""
    data = json.loads(subprocess.check_output([sys.executable, '-c', code, str(BUILD / 'references.bib')], text=True))
    rows = [r'\begin{thebibliography}{GPSR87}']
    for item in sorted(data, key=lambda d: d['key']):
        f = item['fields']
        url = f.get('url') or ('https://doi.org/' + f['doi'] if 'doi' in f else '')
        title = r'\emph{' + f['title'] + '}'
        if url:
            title = r'\href{' + url.replace('%', r'\%').replace('#', r'\#') + '}{' + title + '}'
        row = r'\bibitem[' + item['key'] + ']{' + item['key'] + '}\n' + ' and '.join(item['authors']) + '. ' + title + '. '
        if 'journal' in f:
            row += f['journal'] + ' ' + r'\textbf{' + f.get('volume', '') + '}'
        elif 'booktitle' in f:
            row += 'In ' + f['booktitle']
        elif 'series' in f:
            row += f['series'] + ' ' + f.get('volume', '') + '. ' + f.get('publisher', '')
        else:
            row += f.get('publisher', '')
        if 'year' in f:
            row += ' (' + f['year'] + ')'
        if 'pages' in f:
            row += ', ' + f['pages']
        row += '. '
        if 'note' in f:
            row += re.sub(r'(?<![a-z0-9])([a-f0-9]{40})(?![a-z0-9])', r'\\nolinkurl{\1}', f['note']) + '.'
        rows.append(row)
    rows.append(r'\end{thebibliography}')
    return '\n\n'.join(rows)


def prepare(built, commit, dirty):
    target = BUILD / 'pdf'
    target.mkdir(parents=True, exist_ok=True)
    text = (BUILD / 'resolution.tex').read_text().split(r'\begin{document}', 1)[1]
    # Keep all mathematics; condense the source paragraphs into short clickable labels.
    pattern = r'(?:\\par\\noindent\\textit\{Lean:\} \\href\{[^}]+\}\{\\texttt\{[^}]+\}(?: \(generated\))?\}\.\s*)+'

    def sources(m):
        urls = re.findall(r'\\href\{([^}]+)\}', m[0])
        n = len(urls)
        links = [r'\href{' + lean_url(url) + '}{Lean' + (' ' + str(i + 1) if n > 1 else '') + '}'
                 for i, url in enumerate(urls)]
        return '\n' + r'\par\noindent{\scriptsize\sffamily ' + r'\quad '.join(links) + '}\n'
    text = re.sub(pattern, sources, text)
    if r'\textit{Lean:}' in text:
        raise ValueError('A Lean paragraph was not condensed')
    text = re.sub(r'\\hypertarget\{context-[^}]+\}', '', text)
    tags = json.loads((ROOT / 'tags.json').read_text())
    statements = {v['label'] for v in json.loads((EVIDENCE / 'statement-map.json').read_text())['items']}
    tagged = []

    def heading_tag(m):
        key = m[2]
        if key not in statements:
            raise ValueError('Unmapped statement heading: ' + key)
        tagged.append(key)
        return r'\renewcommand{\statementtag}{' + tags[key] + '}\n' + m[0]
    text = re.sub(r'\\begin\{(' + HEADINGS + r')\}' + OPTIONAL + r'\s*\\label\{([^}]+)\}', heading_tag, text)
    if set(tagged) != statements or len(tagged) != len(statements):
        raise ValueError('Every statement must receive exactly one heading tag')

    def label(m):
        return m[0] + r'\hypertarget{' + tags[m[1]] + '}{}'
    text = re.sub(r'\\label\{([^}]+)\}', label, text)
    text = text.replace(r'\bibliographystyle{alpha}', r'\clearpage\phantomsection\addcontentsline{toc}{chapter}{Bibliography}')
    text = text.replace(r'\bibliography{references}', bibliography_tex())
    lock = json.loads((ROOT / 'toolchain.lock.json').read_text())
    preamble = (PREAMBLE.replace('@TITLE@', TITLE).replace('@BUILT@', build_line(built, commit, dirty))
                .replace('@SHA@', lock['lean']['archive_sha256']))
    (target / 'book.tex').write_text(preamble + text)
    shutil.copy2(BUILD / 'references.bib', target / 'references.bib')
    return target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--engine', default='xelatex')
    args = ap.parse_args()
    engine = shutil.which(args.engine)
    if not engine:
        raise SystemExit('PDF engine not found: ' + args.engine + '; install TeX Live with XeLaTeX')
    built = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    stamp = built.strftime('%Y%m%d-%H%MZ')
    book_file = BOOK_STEM + '-' + stamp + '.pdf'
    commit, dirty = revision()
    target = prepare(built, commit, dirty)
    with (target / 'compile.log').open('w') as log:
        for _ in range(3):
            subprocess.run([engine, '-interaction=nonstopmode', '-halt-on-error', 'book.tex'],
                           cwd=target, env=tex_environment(), stdout=log, stderr=subprocess.STDOUT, check=True)
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject, DictionaryObject, TextStringObject

    class Reader(PdfReader):
        # On writing a chapter, pypdf looks up the book's named destinations once for every link
        # it carries over, and rebuilds them each time; with 16,000 of them that took hours.
        @functools.cached_property
        def named_destinations(self):
            return PdfReader.named_destinations.fget(self)
    reader = Reader(target / 'book.pdf')
    destinations = reader.named_destinations
    pages = {key: reader.get_destination_page_number(value) for key, value in destinations.items()}
    # Only the current build's PDFs are kept.
    if DOWNLOADS.exists():
        shutil.rmtree(DOWNLOADS)
    NAMES.unlink(missing_ok=True)
    DOWNLOADS.mkdir(parents=True)
    shutil.copy2(target / 'book.pdf', DOWNLOADS / book_file)
    shutil.copy2(BUILD / 'references.bib', DOWNLOADS / 'references.bib')
    text = (BUILD / 'resolution.tex').read_text()
    tags = json.loads((ROOT / 'tags.json').read_text())
    boundaries = [(m[1], m[2], m[3]) for m in re.finditer(
        r'\\(part|chapter)\{((?:[^{}]|\{[^{}]*\})*)\}\s*\\label\{([^}]+)\}', text)]
    chapters = []

    def walk(items):
        for entry in items:
            if isinstance(entry, list):
                yield from walk(entry)
            elif entry.title == 'Bibliography':
                yield reader.get_destination_page_number(entry)
    for i, (kind, title, label) in enumerate(boundaries):
        if kind != 'chapter':
            continue
        start = pages[tags[label]]
        # The last chapter ends at the bibliography (located via the PDF outline).
        end = (pages[tags[boundaries[i + 1][2]]] if i + 1 < len(boundaries)
               else next(walk(reader.outline), len(reader.pages)))
        writer = PdfWriter()
        for page in reader.pages[start:end]:
            writer.add_page(page)
        for page in writer.pages:
            for ref in page.get('/Annots', []):
                a = ref.get_object()
                d = a.get('/Dest')
                action = a.get('/A')
                if d is None and action and action.get('/S') == '/GoTo':
                    d = action.get('/D')
                if isinstance(d, str) and d in pages:
                    a.pop('/Dest', None)
                    a[NameObject('/A')] = DictionaryObject({NameObject('/S'): NameObject('/URI'), NameObject('/URI'): TextStringObject(book_file + '#page=' + str(pages[d] + 1))})
        writer.add_metadata({'/Title': re.sub(r'\$', '', title) + ' — ' + TITLE, '/Author': 'Benjamin Antieau'})
        filename = 'chapter-' + tags[label] + '-' + stamp + '.pdf'
        writer.write(DOWNLOADS / filename)
        chapters.append({'tag': tags[label], 'title': title, 'first_page': start + 1, 'last_page': end,
                         'pages': end - start, 'file': filename})
    log = (target / 'book.log').read_text(errors='replace')
    problems = [line for line in log.splitlines() if 'undefined' in line.lower() or 'Missing character:' in line]
    overfull = [line for line in log.splitlines() if line.startswith('Overfull')]
    active = {line.split(',', 1)[0] for line in (BUILD / 'tags.csv').read_text().splitlines() if line}
    report = {'engine': engine, 'pages': len(reader.pages), 'named_destinations': len(destinations),
              'tag_destinations': sum(t in pages for t in active), 'chapters': chapters,
              'typesetting_errors': problems, 'overfull_boxes': len(overfull),
              'overfull_examples': overfull[:20], 'source': 'runtime/build/resolution.tex',
              'file': book_file, 'pdf': 'site/book/' + book_file, 'built': built.isoformat().replace('+00:00', 'Z'),
              'commit': commit, 'uncommitted_changes': dirty}
    (EVIDENCE / 'pdf-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    NAMES.write_text(json.dumps({'built': report['built'], 'stamp': stamp, 'book': book_file,
                                 'chapters': {c['tag']: c['file'] for c in chapters}}, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('chapters', 'overfull_examples')}, indent=2))
    if problems:
        raise SystemExit('Unresolved PDF references or characters')


if __name__ == '__main__':
    main()
