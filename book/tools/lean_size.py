#!/usr/bin/env python3
"""Lines of Lean below a declaration, for the size given beside an open step.

A name in a declaration's text is resolved only to a declaration in the declaration's own file or
in a file it imports (transitively); names bound locally (intro, have, fun, binders, ...) are
skipped. Counting stops at declarations the book already cites in a \\leanref, and at names given
with --stop. The count is the number of lines of the declarations reached, so whole definitions
are counted. Run from lean/rh/book:

    python3 tools/lean_size.py NAME [NAME ...] [--stop NAME ...] [--union] [--per]
        [--minus NAME ...]

--union counts the roots together; --per lists the files with the most lines reached; --minus
reports the lines reached from NAME but not from the --minus roots.
"""
import re, sys, os, sqlite3, functools, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("leanpy", "tools/lean.py")
L = importlib.util.module_from_spec(spec); spec.loader.exec_module(L)
db = sqlite3.connect(L.DB)
SRC = str(L.SRC)
IMP = re.compile(r'^\s*(?:public\s+|private\s+)?(?:meta\s+)?import\s+(?:all\s+)?([\w.«»\']+)')
@functools.lru_cache(None)
def imports(rel):
    p = os.path.join(SRC, rel)
    out = []
    try:
        fh = open(p, encoding='utf-8', errors='replace')
    except OSError:
        return ()
    in_c = False
    for line in fh:
        s = line.strip()
        if s == 'module' or s == 'prelude' or not s or s.startswith('--'): continue
        if in_c:
            if '-/' in s: in_c = False
            continue
        if s.startswith('/-'):
            if '-/' not in s[2:]: in_c = True
            continue
        m = IMP.match(line)
        if m:
            f = m.group(1).replace('.', '/') + '.lean'
            if os.path.exists(os.path.join(SRC, f)): out.append(f)
            continue
        break
    return tuple(out)
_clos = {}
def closure(rel):
    if rel in _clos: return _clos[rel]
    seen = set(); st = [rel]
    while st:
        f = st.pop()
        if f in seen: continue
        seen.add(f); st.extend(imports(f))
    fs = frozenset(seen); _clos[rel] = fs; return fs
@functools.lru_cache(maxsize=20000)
def _lines(rel):
    return (L.SRC / rel).read_text(encoding="utf-8", errors="replace").split("\n")
def _text(row):
    lines = _lines(row[3])
    body = lines[row[4] - 1:row[5]]
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body)
L.text = _text
@functools.lru_cache(maxsize=None)
def _q(name):
    return tuple(db.execute("select * from decls where name = ?", (name,)).fetchall())
cited = set()
for f in Path("manuscript").glob("*.tex"):
    cited.update(re.findall(r"\\leanref\{[^}]*\}\{([^}]*)\}", f.read_text()))
def deps(row):
    clo = closure(row[3])
    seen, out = set(), []
    prefixes = [""]
    parts = row[6].split(".") if row[6] else []
    prefixes += [".".join(parts[:k]) + "." for k in range(1, len(parts) + 1)]
    prefixes += [o + "." for o in row[7].split()]
    t = L.text(row)
    bound = set()
    sig = t.split(":=", 1)[0]
    pats = [(t, r"(?:intro|rintro|intros|obtain|rcases)\s+([^\n:]*)"), (t, r"have\s+([\w'₀-₉]+)"),
            (sig, r"[({\[⦃]\s*([\w'₀-₉ ]+?)\s*:"), (t, r"[∀∃]\s+([\w'₀-₉ ]+)[,:]"),
            (t, r"fun\s+([^=:]*?)\s*(?:=>|↦|:)"), (t, r"fun\s+\(([\w'₀-₉ ]+?)\s*:"),
            (t, r"\|\s*([^\n=]*?)=>"), (t, r"(?:let|set)\s+([\w'₀-₉]+)")]
    for src_, pat in pats:
        for m in re.finditer(pat, src_):
            bound.update(x for x in L.IDENT.findall(m.group(1)) if '.' not in x)
    for tok in L.IDENT.findall(t):
        tok = tok.rstrip(".")
        if tok in bound: continue
        if tok in seen or tok == row[0]: continue
        seen.add(tok)
        for p in prefixes:
            hits = _q(p + tok)
            hits = [h for h in hits if h[3] in clo and h[0] != row[0]]
            if hits:
                out.extend(hits); break
    return out
def reach(roots, stop):
    seen = {}
    st = []
    for n in roots:
        st.extend(L.find(db, n)[:1])
    first = True
    while st:
        r = st.pop()
        key = (r[0], r[3], r[4])
        if key in seen: continue
        if not first and (r[0] in cited or r[0] in stop): continue
        seen[key] = r
        first = False
        for d in deps(r):
            if (d[0], d[3], d[4]) not in seen: st.append(d)
    return seen
args = sys.argv[1:]
roots, stop, minus, per = [], set(), [], False
union = '--union' in args
args = [a for a in args if a != '--union']
mode = 'root'
for a in args:
    if a == '--stop': mode = 'stop'; continue
    if a == '--minus': mode = 'minus'; continue
    if a == '--per': per = True; continue
    {'root': roots, 'minus': minus}.get(mode, None).append(a) if mode != 'stop' else stop.add(a)
def lines(rs):
    return sum(r[5]-r[4]+1 for r in rs), sum(r[5]-r[4]+1 for r in rs if r[2] in ('theorem','lemma')), sum(1 for r in rs if r[2] in ('theorem','lemma'))
groups = [roots] if union else [[r] for r in roots]
for grp in groups:
    root = '+'.join(grp)
    s = {}
    for r0 in grp: s.update(reach([r0], stop))
    a, b, c = lines(s.values())
    msg = f"{root}: {a} lines in {len(s)} declarations, of which {b} lines in {c} theorems"
    if minus:
        o = {}
        for m in minus: o.update(reach([m], stop))
        rest = {k: v for k, v in s.items() if k not in o}
        a, b, c = lines(rest.values())
        msg += f"; not below the --minus roots: {a} lines, {b} in {c} theorems"
    print(msg)
    if per:
        byf = {}
        for r in s.values(): byf[r[3]] = byf.get(r[3], 0) + r[5]-r[4]+1
        for f, n in sorted(byf.items(), key=lambda x: -x[1])[:25]: print(f"   {n:7d} {f}")
