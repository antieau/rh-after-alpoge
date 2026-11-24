"""Find declarations in Alpöge's Lean sources without building them (run from the book directory).

Usage:
  python3 tools/lean.py index            # build runtime/decls.sqlite from runtime/source (a few minutes)
  python3 tools/lean.py find NAME        # declarations whose full name is NAME or ends in .NAME
  python3 tools/lean.py show NAME        # the source text of those declarations
  python3 tools/lean.py deps NAME        # the archive's declarations that NAME's text mentions

The index reads the text only: full names come from `namespace`/`section`/`end` blocks, and `deps`
resolves identifiers through the current namespaces and the file's `open` lines. Both are close
approximations; the Lean build is the authority.
"""
import os
import re
import sqlite3
import sys
from multiprocessing import Pool
from pathlib import Path

BOOK = Path(__file__).resolve().parent.parent
SRC = BOOK / "runtime" / "source" / "lean" / "src"
DB = BOOK / "runtime" / "decls.sqlite"

MODS = r"(?:(?:private|protected|noncomputable|partial|unsafe|nonrec|scoped|local)\s+)*"
DECL = re.compile(r"^(?:@\[[^\]]*\]\s*)*" + MODS +
                  r"(theorem|lemma|def|abbrev|instance|structure|class|inductive|opaque|axiom)\b\s*([^\s:({\[⦃]*)")
BLOCK = re.compile(r"^(namespace|section|noncomputable section|end)\b\s*([\w.'«»]*)")
OPEN = re.compile(r"^open\s+(?:scoped\s+)?([^\n]*?)(?:\s+in\s*$|$)")
IDENT = re.compile(r"[A-Za-z_Ͱ-Ͽᴀ-ᶿ][\w.'!?Ͱ-Ͽ₀-ₜᴀ-ᶿ]*")


def scan(path):
    rows, opens, stack = [], set(), []
    lines = path.read_text(encoding="utf-8", errors="replace").split("\n")
    rel = str(path.relative_to(SRC))
    for i, line in enumerate(lines, 1):
        if line.startswith(" ") or line.startswith("\t"):
            continue
        m = BLOCK.match(line)
        if m:
            kind, name = m.groups()
            if kind == "namespace":
                stack.append(("ns", name))
            elif kind == "end":
                if stack:
                    stack.pop()
            else:
                stack.append(("sec", name))
            continue
        m = OPEN.match(line)
        if m:
            opens.update(w for w in m.group(1).split() if not w.startswith("("))
            continue
        m = DECL.match(line)
        if m:
            kind, name = m.groups()
            ns = ".".join(n for k, n in stack if k == "ns" and n)
            if kind == "instance" and (not name or name.startswith("[")):
                name = f"<instance at line {i}>"
            if name.startswith("_root_."):
                full = name[7:]
            else:
                full = f"{ns}.{name}" if ns else name
            rows.append([full, full.rsplit(".", 1)[-1], kind, rel, i, len(lines), ns, " ".join(sorted(opens))])
    for a, b in zip(rows, rows[1:]):
        a[5] = b[4] - 1
    return rows


def index():
    files = sorted(SRC.rglob("*.lean"))
    if DB.exists():
        DB.unlink()
    db = sqlite3.connect(DB)
    db.execute("create table decls (name, last, kind, file, line, end_line, ns, opens)")
    with Pool(os.cpu_count()) as pool:
        for rows in pool.imap_unordered(scan, files, chunksize=200):
            db.executemany("insert into decls values (?,?,?,?,?,?,?,?)", rows)
    db.execute("create index by_name on decls(name)")
    db.execute("create index by_last on decls(last)")
    db.commit()
    n = db.execute("select count(*) from decls").fetchone()[0]
    print(f"{n} declarations from {len(files)} files in {DB}")


def find(db, name):
    rows = db.execute("select * from decls where name = ?", (name,)).fetchall()
    if not rows:
        last = name.rsplit(".", 1)[-1]
        rows = [r for r in db.execute("select * from decls where last = ?", (last,))
                if r[0].endswith("." + name) or r[0] == name]
    return rows


def text(row):
    lines = (SRC / row[3]).read_text(encoding="utf-8", errors="replace").split("\n")
    body = lines[row[4] - 1:row[5]]
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body)


def deps(db, row):
    seen, out = set(), []
    prefixes = [""]
    parts = row[6].split(".") if row[6] else []
    prefixes += [".".join(parts[:k]) + "." for k in range(1, len(parts) + 1)]
    prefixes += [o + "." for o in row[7].split()]
    for tok in IDENT.findall(text(row).split(":=", 1)[-1] + " " + text(row).split(":=", 1)[0]):
        tok = tok.rstrip(".")
        if tok in seen or tok == row[0]:
            continue
        seen.add(tok)
        for p in prefixes:
            hit = db.execute("select name, file, line from decls where name = ?", (p + tok,)).fetchone()
            if hit and hit[0] != row[0]:
                out.append(hit)
                break
    return out


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in {"index", "find", "show", "deps"}:
        sys.exit(__doc__)
    if sys.argv[1] == "index":
        return index()
    db = sqlite3.connect(DB)
    for name in sys.argv[2:]:
        rows = find(db, name)
        if not rows:
            print(f"{name}: not found")
        for r in rows:
            print(f"{r[0]}  ({r[2]})  {r[3]}:{r[4]}")
            if sys.argv[1] == "show":
                print(text(r) + "\n")
            elif sys.argv[1] == "deps":
                for d in deps(db, r):
                    print(f"  {d[0]}  {d[1]}:{d[2]}")


if __name__ == "__main__":
    main()
