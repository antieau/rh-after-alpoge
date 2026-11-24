"""Render the book's status page, plan and Lean source pages into site/ (run from the book directory).

Usage: python3 tools/render.py

Reads manuscript/, plan/, status.json, runtime/status/ and the Git history, and writes
site/index.html (where the work stands), site/plan.html (the chapter plan), site/src/ (every Lean
file that the plan, the manuscript or the built book cites, with an anchor #L<line> on each line)
and site/read.html, which now forwards to the Gerby book's reader. It copies explorer/ to
site/explorer/ and writes the explorer's data, site/explorer/rh.graph.json, with
tools/explorer_data.py. The book itself is site/book/, built by tools/build.py.

The links to the PDFs go to the files now in site/book/, whose names carry their build time, and
site/_redirects sends the old names (/book/book.pdf, /book/chapter-<TAG>.pdf) to them.
"""
import functools
import html
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BOOK = Path(__file__).resolve().parent.parent
MANUSCRIPT = BOOK / "manuscript"
PLAN = BOOK / "plan"
SRC = BOOK / "runtime" / "source" / "lean" / "src"
DECLS = BOOK / "runtime" / "decls.sqlite"
SITE = BOOK / "site"
EXPLORER = BOOK / "explorer"

STATES = ["mapping", "planned", "drafting", "drafted", "reviewed"]
CSS = """
:root { --bg: #fbfaf7; --fg: #1d1d1b; --muted: #6b6a66; --rule: #e3e0d8; --panel: #f3f1ec;
  --accent: #6b4fbb; --ok: #2f7d4f; --warn: #a3620a; --bad: #b3261e; --code: #f1eee7; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg: #161614; --fg: #e8e6e1;
  --muted: #9b9890; --rule: #34322e; --panel: #201f1c; --accent: #a993f0; --ok: #6cc08f;
  --warn: #e0a54a; --bad: #f08a80; --code: #23221f; } }
:root[data-theme="dark"] { --bg: #161614; --fg: #e8e6e1; --muted: #9b9890; --rule: #34322e;
  --panel: #201f1c; --accent: #a993f0; --ok: #6cc08f; --warn: #e0a54a; --bad: #f08a80; --code: #23221f; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 17px/1.6 "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif; }
main { max-width: 860px; margin: 0 auto; padding: 32px 16px 80px; }
nav { font: 14px/1.4 system-ui, sans-serif; display: flex; gap: 18px; flex-wrap: wrap;
  border-bottom: 1px solid var(--rule); padding-bottom: 10px; margin-bottom: 28px; }
nav a { color: var(--muted); text-decoration: none; } nav a.here { color: var(--fg); font-weight: 600; }
a { color: var(--accent); }
h1 { font-size: 30px; line-height: 1.2; margin: 0 0 8px; font-weight: 600; }
h2 { font-size: 22px; margin: 40px 0 12px; font-weight: 600; }
h3 { font-size: 18px; margin: 28px 0 8px; font-weight: 600; }
.lede { color: var(--muted); margin: 0 0 24px; }
.small, .meta, table, .tiles, .badge, .leanref, footer { font-family: system-ui, sans-serif; }
.small { font-size: 14px; color: var(--muted); }
.panel { background: var(--panel); border: 1px solid var(--rule); border-radius: 8px; padding: 16px 18px; margin: 16px 0; }
.panel h2 { margin-top: 0; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; margin: 16px 0; }
.tile { border: 1px solid var(--rule); border-radius: 8px; padding: 10px 12px; }
.tile b { display: block; font-size: 24px; font-weight: 600; }
.tile span { font-size: 13px; color: var(--muted); }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; vertical-align: top; padding: 8px 6px; border-bottom: 1px solid var(--rule); }
th { color: var(--muted); font-weight: 500; }
.badge { display: inline-block; font-size: 12px; padding: 1px 8px; border-radius: 10px; border: 1px solid currentColor; white-space: nowrap; }
.s-mapping, .s-searching, .s-building, .s-extracting { color: var(--warn); }
.s-planned, .s-drafting { color: var(--accent); }
.s-drafted, .s-reviewed, .s-done, .s-built { color: var(--ok); }
.s-blocked, .s-failed { color: var(--bad); }
.env { margin: 18px 0; } .env > p:first-child b { font-weight: 600; }
.env-definition, .env-remark, .env-example, .env-situation, .env-notation { }
.env-theorem, .env-lemma, .env-proposition, .env-corollary { font-style: italic; }
.env-theorem .MathJax, .env-lemma .MathJax { font-style: normal; }
.proof { margin: 8px 0 18px; } .qed { float: right; }
.transition { color: var(--muted); }
.leanref { font-size: 13px; margin: -10px 0 14px; color: var(--muted); }
.leanref a { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.statement { margin: 10px 0 14px; padding-left: 12px; border-left: 3px solid var(--rule); }
.role { font: 12px system-ui, sans-serif; color: var(--muted); }
pre.lean { font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; background: var(--code);
  padding: 12px 0; overflow-x: auto; border-radius: 6px; }
pre.lean span.l { display: block; padding: 0 12px; } pre.lean span.l:target { background: rgba(107,79,187,.18); }
pre.lean span.n { display: inline-block; width: 4.5em; color: var(--muted); user-select: none; }
footer { margin-top: 48px; font-size: 12px; color: var(--muted); border-top: 1px solid var(--rule); padding-top: 12px; overflow-wrap: anywhere; }
@media (max-width: 600px) { body { font-size: 16px; } .hide-narrow { display: none; } }
"""

RELATIVE_TIME = """
<script>
for (const t of document.querySelectorAll('time[datetime]')) {
  const s = (Date.now() - Date.parse(t.getAttribute('datetime'))) / 1000;
  if (isNaN(s)) continue;
  const r = s < 90 ? 'just now' : s < 5400 ? Math.round(s / 60) + ' min ago'
    : s < 129600 ? Math.round(s / 3600) + ' h ago' : Math.round(s / 86400) + ' days ago';
  t.title = t.textContent; t.textContent = r;
}
</script>
"""


def load(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def git(*args):
    r = subprocess.run(["git", "-C", str(BOOK), *args], capture_output=True, text=True)
    return r.stdout.strip()


def esc(s):
    return html.escape(str(s), quote=True)


def when(iso):
    if not iso:
        return ""
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return esc(iso)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    t = t.astimezone(timezone.utc)
    return f'<time datetime="{t.isoformat()}">{t.strftime("%d %b %H:%M UTC")}</time>'


def prose(text):
    """Plain text with $math$ and blank-line paragraphs, as the plan files hold it."""
    return "".join(f"<p>{esc(p.strip())}</p>" for p in re.split(r"\n\s*\n", text or "") if p.strip())


def macros():
    out = {}
    path = MANUSCRIPT / "macros.tex"
    if path.exists():
        for m in re.finditer(r"\\(?:re)?newcommand\{?\\(\w+)\}?(?:\[(\d)\])?\{(.*)\}\s*$|"
                             r"\\DeclareMathOperator\*?\{\\(\w+)\}\{(.*)\}\s*$", path.read_text(), re.M):
            if m.group(1):
                out[m.group(1)] = [m.group(3), int(m.group(2))] if m.group(2) else m.group(3)
            else:
                out[m.group(4)] = r"\operatorname{" + m.group(5) + "}"
    return out


@functools.lru_cache(maxsize=None)
def current_pdfs():
    """The PDFs now in site/book/, named with their build time (tools/build_pdf.py): the book's file
    name and the chapters' by tag, or (None, {}) before the first build."""
    stamps = sorted(m[1] for p in (SITE / "book").glob("rh-after-alpoge-*.pdf")
                    if (m := re.fullmatch(r"rh-after-alpoge-(\d{8}-\d{4}Z)\.pdf", p.name)))
    if not stamps:
        return None, {}
    stamp = stamps[-1]
    chapters = {m[1]: p.name for p in (SITE / "book").glob("chapter-*-" + stamp + ".pdf")
                if (m := re.fullmatch(r"chapter-([0-9A-Z]{4})-" + stamp + r"\.pdf", p.name))}
    return "rh-after-alpoge-" + stamp + ".pdf", chapters


def write_redirects():
    """site/_redirects, which Workers static assets read (and do not serve): the PDFs' old names go to
    the current files with a 302, so that old links keep working."""
    book, chapters = current_pdfs()
    path = SITE / "_redirects"
    if not book:
        path.unlink(missing_ok=True)
        return
    lines = [f"/book/book.pdf /book/{book} 302"]
    lines += [f"/book/chapter-{tag}.pdf /book/{name} 302" for tag, name in sorted(chapters.items())]
    path.write_text("\n".join(lines) + "\n")


def page(title, here, body, refresh=False, depth=0):
    up = "../" * depth
    book_pdf = current_pdfs()[0]
    links = [("status.html", "Status"), ("plan.html", "Plan"), ("book/index.html", "Book"),
             ("book/read.html", "Read")] + ([("book/" + book_pdf, "PDF")] if book_pdf else []) + [
             ("explorer/index.html", "Explorer")]
    nav = "".join(f'<a href="{up}{h}"{" class=here" if h == here else ""}>{t}</a>' for h, t in links)
    mj = json.dumps({"tex": {"inlineMath": [["$", "$"], ["\\(", "\\)"]], "macros": macros()},
                     "chtml": {"scale": 0.95}})
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
{'<meta http-equiv="refresh" content="120">' if refresh else ''}
<title>{esc(title)}</title>
<link rel="icon" type="image/png" sizes="192x192" href="{up}book/static/zeta-favicon.png">
<link rel="icon" type="image/svg+xml" href="{up}book/static/zeta-favicon.svg">
<link rel="stylesheet" href="{up}style.css">
<script>window.MathJax = {mj};</script>
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.min.js"></script>
</head><body><main>
<nav>{nav}<a href="https://alpo.ge/remark.pdf">Alpöge's announcement</a></nav>
{body}
<footer>A reading of Levent Alpöge's Lean proof; a working draft, not Alpöge's own exposition.
Rendered {when(datetime.now(timezone.utc).isoformat())}.<br>Created by Benjamin Antieau at Resolution.</footer>
</main>{RELATIVE_TIME}</body></html>
"""


def chapters():
    out = []
    for path in sorted((PLAN / "chapters").glob("*.json")):
        c = load(path)
        if isinstance(c, dict):
            c.setdefault("id", path.stem)
            c["_file"] = path.name
            out.append(c)
    return out


def badge(state):
    return f'<span class="badge s-{esc(state or "planned")}">{esc(state or "planned")}</span>'


def src_link(depth, file, line=None, name=None):
    anchor = f"#L{line}" if line else ""
    return f'{"../" * depth}src/{esc(file)}.html{anchor}'


# ---------------------------------------------------------------- the manuscript


def strip_comments(text):
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in text.split("\n"))


def cited_files(book):
    """The Lean files that the manuscript cites now and that the built book cites."""
    files = set()
    for e in book.get("entries", []):
        path = MANUSCRIPT / e.get("file", "")
        if path.is_file():
            files |= {f for f, _ in re.findall(r"\\leanref\{([^}]*)\}\{([^}]*)\}", strip_comments(path.read_text()))}
    files |= {r["path"] for r in load(BOOK / "runtime" / "evidence" / "source-links.json", [])}
    return files


REDIRECT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex, nofollow">
<meta http-equiv="refresh" content="0; url=book/read.html"><title>The book</title></head>
<body><p>The draft is now the tagged book: <a href="book/read.html">read it here</a>.</p></body></html>
"""


# ---------------------------------------------------------------- plan and status


def render_plan(chs):
    overview = load(PLAN / "overview.json", {})
    body = ["<h1>The plan of the book</h1>",
            '<p class="lede">How the proof goes, and the chapters it will be told in. Each statement links'
            " to its place in Alpöge's Lean.</p>"]
    if overview.get("overview"):
        body.append(f"<h2>How the proof goes</h2>{prose(overview['overview'])}")
    for i, c in enumerate(chs, 1):
        body.append(f'<h2 id="{esc(c["id"])}">{i}. {esc(c.get("title", c["id"]))} {badge(c.get("state"))}</h2>')
        body.append(prose(c.get("summary", "")))
        if c.get("timeline"):
            body.append(f'<p class="small">Announcement timeline, steps {esc(", ".join(map(str, c["timeline"])))}.</p>')
        for s in c.get("statements", []):
            ref = f' {esc(s["reference"])}' if s.get("reference") else ""
            link = (f' <a href="{src_link(0, s["file"], s.get("line"))}"><code>{esc(s.get("lean", ""))}</code></a>'
                    if s.get("file") else f' <code>{esc(s.get("lean", ""))}</code>')
            body.append(f'<div class="statement">{prose(s.get("statement", ""))}'
                        f'<div class="role">{esc(s.get("role", ""))}{ref} ·{link}</div></div>')
    if not chs:
        body.append("<p>The proof is being mapped; chapters appear here as they are settled.</p>")
    return page("Plan", "plan.html", "\n".join(body))


def open_steps():
    """(chapter title, label of the statement it belongs to, text) for each open step."""
    titles = {e["file"]: e.get("title", e["file"]) for e in load(MANUSCRIPT / "book.json", {}).get("entries", [])}
    out = []
    for path in MANUSCRIPT.glob("*.tex"):
        if path.name.startswith("transitions") or path.name not in titles:
            continue
        text = path.read_text()
        marks = [(m.start(), "Not yet written out in the book.")
                 for m in re.finditer(r"(?m)^[ \t]*%[ \t]*OPEN:.*", text)]
        i = 0
        while (i := text.find("\\openstep{", i)) >= 0:
            depth, j = 0, i + len("\\openstep")
            for j in range(j, len(text)):
                depth += {"{": 1, "}": -1}.get(text[j], 0) if text[j - 1] != "\\" else 0
                if depth == 0:
                    break
            line_start = text.rfind("\n", 0, i) + 1
            if not text[line_start:i].lstrip().startswith("%"):
                marks.append((i, " ".join(text[i + len("\\openstep{"):j].split())))
            i = j + 1
        for start, body in sorted(marks):
            labels = re.findall(r"\\label\{([^}]*)\}", strip_comments(text[:start]))
            out.append((titles[path.name], labels[-1] if labels else "", body))
    order = list(titles.values())
    return sorted(out, key=lambda o: order.index(o[0]))


def render_open_steps():
    steps = open_steps()
    if not steps:
        return ""
    tags = load(BOOK / "tags.json", {})
    rows = "".join(
        f'<tr><td class="small">{esc(ch)}</td><td>'
        + (f'<a href="book/tag/{esc(tags[label])}.html">{esc(label)}</a>' if label in tags else esc(label))
        + f'<div class="small">{esc(body)}</div></td></tr>' for ch, label, body in steps)
    return (f"<h2>Open steps ({len(steps)})</h2><p class=small>Steps of the proof the book does not yet carry"
            " out. Each is marked in the text where it occurs.</p>"
            f"<table><tr><th>Chapter</th><th>Statement</th></tr>{rows}</table>")


def manuscript_counts():
    text = "\n".join(strip_comments(p.read_text()) for p in MANUSCRIPT.glob("*.tex")
                     if not p.name.startswith("transitions"))
    statements = len(re.findall(r"\\begin\{(?:theorem|lemma|proposition|corollary|definition)\}", text))
    proofs = len(re.findall(r"\\begin\{proof\}", text))
    links = len(re.findall(r"\\leanref\{", text))
    opens = len(open_steps())
    r = subprocess.run([sys.executable, str(BOOK / "tools" / "check_style.py")], capture_output=True,
                       text=True, cwd=BOOK)
    warnings = len([l for l in r.stdout.splitlines() if l.strip()])
    return statements, proofs, links, warnings, opens


def render_agents():
    """The agents at work now, and those that finished in the last day, from runtime/status/agents/."""
    now = datetime.now(timezone.utc)
    rows = []
    for path in (BOOK / "runtime" / "status" / "agents").glob("*.json"):
        a = load(path, {})
        try:
            age = (now - datetime.fromisoformat(str(a.get("updated")).replace("Z", "+00:00"))).total_seconds()
        except ValueError:
            continue
        if a.get("state") == "running" or age < 86400:
            rows.append((a.get("state") != "running", -age if a.get("state") == "running" else age, a))
    if not rows:
        return ""
    rows.sort(key=lambda r: (r[0], r[1]))
    body = "".join(
        f'<tr><td>{esc(a.get("agent", ""))}<div class="small">{esc(a.get("progress", ""))}</div></td>'
        f'<td>{badge("drafting" if a.get("state") == "running" else "done")}</td>'
        f'<td class="hide-narrow">{when(a.get("updated"))}</td></tr>' for _, _, a in rows)
    running = sum(1 for done, _, _ in rows if not done)
    return (f"<h2>Now: {running} agent{'s' if running != 1 else ''} at work</h2>"
            f"<table><tr><th>Task</th><th>State</th><th class=hide-narrow>Updated</th></tr>{body}</table>")


def render_status(chs):
    st = load(BOOK / "status.json", {})
    build = load(BOOK / "runtime" / "status" / "build.json", {})
    source = load(BOOK / "source.json", {})
    statements, proofs, links, warnings, opens = manuscript_counts()
    mapped = sum(len(c.get("statements", [])) for c in chs)
    body = [
        "<h1>The Riemann Hypothesis after Alpöge</h1>",
        '<p class="lede">A reading of Levent Alpöge\'s Lean proof of the Riemann Hypothesis and of the'
        " Generalized Riemann Hypothesis for Dirichlet $L$-functions; a working draft, not Alpöge's own"
        " exposition. This page shows where the work stands and refreshes every two minutes.</p>",
        f'<div class="panel"><h2>{esc(st.get("phase", "Starting"))}</h2>{prose(st.get("summary", ""))}'
        f'<p class="small">Updated {when(st.get("updated"))}</p></div>',
        '<div class="tiles">'
        f'<div class="tile"><b>{len(chs)}</b><span>chapters planned</span></div>'
        f'<div class="tile"><b>{mapped}</b><span>statements mapped</span></div>'
        f'<div class="tile"><b>{statements}</b><span>statements drafted</span></div>'
        f'<div class="tile"><b>{proofs}</b><span>proofs drafted</span></div>'
        f'<div class="tile"><b>{links}</b><span>links to the Lean</span></div>'
        f'<div class="tile"><b>{opens}</b><span>steps still OPEN</span></div>'
        "</div>",
    ]
    body.append(render_agents())
    if st.get("next"):
        body.append("<h2>Next</h2><ul>" + "".join(f"<li>{esc(n)}</li>" for n in st["next"]) + "</ul>")
    body.append("<h2>Chapters</h2>")
    if chs:
        rows = "".join(
            f'<tr><td>{i}</td><td><a href="plan.html#{esc(c["id"])}">{esc(c.get("title", c["id"]))}</a>'
            f'<div class="small">{esc(c.get("progress", ""))}</div></td><td>{badge(c.get("state"))}</td>'
            f'<td>{len(c.get("statements", []))}</td><td class="hide-narrow">{when(c.get("updated"))}</td></tr>'
            for i, c in enumerate(chs, 1))
        body.append("<table><tr><th>#</th><th>Chapter</th><th>State</th><th>Statements</th>"
                    f'<th class="hide-narrow">Updated</th></tr>{rows}</table>')
    else:
        body.append("<p>The proof is being mapped; the chapters appear here as they are settled.</p>")
    book_build = load(BOOK / "runtime" / "status" / "book.json", {})
    body.append("<h2>The book</h2>")
    book_pdf = current_pdfs()[0]
    if (SITE / "book" / "index.html").exists():
        parts = ('The tagged <a href="book/index.html">book</a>, its <a href="book/read.html">complete text</a>'
                 f' and <a href="book/{esc(book_pdf)}">PDF</a>' if book_pdf else
                 'The tagged <a href="book/index.html">book</a> and its <a href="book/read.html">complete text</a>')
        body.append(f"<p>{parts} are built from the manuscript with Gerby, the software of the Stacks Project,"
                    " about every ten minutes while the manuscript changes.</p>")
    else:
        body.append("<p>The tagged book has not been built yet.</p>")
    if book_build:
        counts = book_build.get("counts") or {}
        extra = (f'{counts.get("tags", 0)} tags, {counts.get("statements", 0)} statements,'
                 f' {counts.get("pages", 0)} PDF pages, {counts.get("overfull_boxes", 0)} overfull lines.' if book_build.get("state") == "built" and counts else "")
        body.append(f'<p>Last build {badge(book_build.get("state"))} {esc(book_build.get("detail", ""))}{esc(extra)}'
                    f' <span class="small">{when(book_build.get("updated"))}, {book_build.get("seconds", 0)} s</span></p>')
    body.append("<h2>The Lean</h2>")
    if build:
        body.append(f'<p>Build and extraction {badge(build.get("state"))} {esc(build.get("detail", ""))}'
                    f' <span class="small">{when(build.get("updated"))}</span></p>')
    body.append(f'<p class="small">Alpöge\'s archive: 175,187 files, 17.4 million lines, {esc(source.get("toolchain", ""))},'
                f' Mathlib {esc(source.get("mathlib", {}).get("rev", "")[:10])}. Style checker: {warnings} warnings.</p>')
    spend = load(BOOK / "runtime" / "status" / "spend.json")
    if spend:
        cl = spend.get("cluster") or {}
        body.append("<h2>Spend</h2>")
        body.append(
            '<div class="tiles">'
            f'<div class="tile"><b>${spend.get("agents_usd", 0):,.0f}</b><span>Claude agents</span></div>'
            f'<div class="tile"><b>{cl.get("core_hours", 0):,.0f}</b><span>core-hours on the cluster</span></div>'
            "</div>")
        rows = "".join(f'<tr><td>{esc(a["agent"])}</td><td>${a["usd"]:,.2f}</td>'
                       f'<td class="hide-narrow">{a["tokens"] / 1e6:,.1f}M</td></tr>'
                       for a in spend.get("agents", [])[:12])
        body.append(f"<table><tr><th>Agent</th><th>Cost</th><th class=hide-narrow>Tokens</th></tr>{rows}</table>")
        note = (f'Agents are priced at list price with the {esc(spend.get("prices", ""))} table that Risen uses,'
                f' counted from {when(spend.get("since"))}.')
        if spend.get("unpriced_models"):
            note += f' Calls to {esc(", ".join(spend["unpriced_models"]))} are not in that table and count as $0.'
        note += (f' The cluster figure is the build machine\'s {cl.get("cores", 0):.0f} cores times the hours it has'
                 " run, plus a 1 TiB volume; no dollar rate for the cluster is recorded here.")
        body.append(f'<p class="small">{note}</p>')
    body.append(render_open_steps())
    log = git("log", "-n", "12", "--format=%h%x09%aI%x09%s", "--", ".")
    changed = [l for l in git("status", "--porcelain", "--", ".").splitlines() if l.strip()]
    body.append("<h2>Recent work</h2>")
    if changed:
        body.append(f'<p class="small">{len(changed)} files changed since the last commit.</p>')
    if log:
        body.append("<table>" + "".join(
            f"<tr><td class=small>{when(d)}</td><td>{esc(s)}</td></tr>"
            for h, d, s in (l.split("\t", 2) for l in log.splitlines())) + "</table>")
    for note in st.get("log", [])[:12]:
        body.append(f'<p class="small">{when(note.get("time"))} · {esc(note.get("text", ""))}</p>')
    return page("RH after Alpöge: status", "status.html", "\n".join(body), refresh=True)


# ---------------------------------------------------------------- Lean sources


def render_sources(files):
    names = {f: {} for f in files}
    if DECLS.exists() and files:
        # One pass over the index: it has no index by file.
        db = sqlite3.connect(DECLS)
        wanted = sorted(files)
        for start in range(0, len(wanted), 500):
            chunk = wanted[start:start + 500]
            for name, f, line in db.execute("select name, file, line from decls where file in (%s)"
                                            % ",".join("?" * len(chunk)), chunk):
                names[f][line] = name
    for f in sorted(files):
        path = SRC / f
        if not path.exists() or ".." in Path(f).parts:
            continue
        depth = len(Path(f).parts)
        lines = path.read_text(encoding="utf-8", errors="replace").split("\n")
        body = []
        for i, line in enumerate(lines, 1):
            anchor = f'<a id="{esc(names.get(f, {})[i])}"></a>' if i in names.get(f, {}) else ""
            body.append(f'<span class="l" id="L{i}">{anchor}<span class="n">{i}</span>{esc(line)}</span>')
        out = SITE / "src" / (f + ".html")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page(f, "", f'<h1 class="small">{esc(f)}</h1><pre class="lean">{"".join(body)}</pre>',
                            depth=depth))


def brief_status():
    """Put a short status line on the book's landing page, between markers, each time it is rendered."""
    path = SITE / "book" / "index.html"
    if not path.exists():
        return
    st = load(BOOK / "status.json", {})
    statements, proofs, _, _, opens = manuscript_counts()
    note = (f'<!--rh-status--><div style="border-left:3px solid #5b6b82;padding:.45rem .9rem;margin:1.2rem 0;'
            f'font-size:.95rem"><strong>Status.</strong> {esc(st.get("phase", ""))}. '
            f'{len(chapters())} chapters, {statements} statements, {proofs} proofs; '
            f'{opens} open step{"s" if opens != 1 else ""}, each marked in the text. '
            f'<a href="../status.html">Details</a> · <a href="../explorer/index.html">Explorer</a>'
            f' · updated {when(st.get("updated"))}</div><!--/rh-status-->')
    html_text = path.read_text()
    if "<!--rh-status-->" in html_text:
        html_text = re.sub(r"<!--rh-status-->.*?<!--/rh-status-->", lambda m: note, html_text, flags=re.S)
    else:
        html_text = html_text.replace('<ul class="home-reading-links">', note + '\n  <ul class="home-reading-links">', 1)
    html_text = html_text.replace('href="../index.html">Where the work stands', 'href="../status.html">Where the work stands')
    path.write_text(html_text)


def render_explorer():
    """Copy explorer/ (the page, its adapter and the pinned Tau Ceti Explorer files, without the tests and
    the notes) into site/explorer/, and write its data with tools/explorer_data.py. A failure is reported
    and leaves the previous data in place; it does not stop the rest of the site."""
    out = SITE / "explorer"
    if not EXPLORER.is_dir():
        return "explorer: no explorer/ directory"
    wanted = {path.relative_to(EXPLORER): path for path in EXPLORER.rglob("*")
              if path.is_file() and not path.name.endswith(".test.mjs") and path != EXPLORER / "README.md"}
    for rel, path in wanted.items():
        target, data = out / rel, path.read_bytes()
        if not target.is_file() or target.read_bytes() != data:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    for path in sorted(out.rglob("*"), reverse=True):
        if (path.is_file() and path.relative_to(out) not in wanted and path.name != "rh.graph.json"
                and not path.name.startswith(".rh.graph.")):  # explorer_data.py's file being written
            path.unlink()
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    r = subprocess.run([sys.executable, str(BOOK / "tools" / "explorer_data.py"), "--out", str(out / "rh.graph.json")],
                       capture_output=True, text=True)
    if r.returncode:
        print("tools/explorer_data.py failed; the previous explorer data stays.\n" + r.stderr[-3000:], file=sys.stderr)
        return "explorer: data not written"
    return r.stdout.strip()


def main():
    SITE.mkdir(exist_ok=True)
    (SITE / "style.css").write_text(CSS)
    book = load(MANUSCRIPT / "book.json", {})
    chs = chapters()
    (SITE / "read.html").write_text(REDIRECT)
    (SITE / "plan.html").write_text(render_plan(chs))
    (SITE / "status.html").write_text(render_status(chs))
    # The book is the landing page; the root sends readers there.
    (SITE / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex">'
        '<meta http-equiv="refresh" content="0; url=book/index.html"><title>The Riemann Hypothesis after Alpöge</title>'
        '<p><a href="book/index.html">The Riemann Hypothesis after Alpöge</a></p>\n')
    brief_status()
    files = cited_files(book) | {s["file"] for c in chs for s in c.get("statements", []) if s.get("file")}
    # The pages of files that are no longer cited stay, so that old links to them work, and are
    # rendered again with the rest, so that their own links stay current.
    files |= {p.relative_to(SITE / "src").as_posix()[:-len(".html")] for p in (SITE / "src").rglob("*.html")}
    render_sources(files)
    (SITE / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    write_redirects()
    print(f"rendered {SITE}: {len(chs)} chapters planned, {len(files)} Lean files")
    print(render_explorer())


if __name__ == "__main__":
    main()
