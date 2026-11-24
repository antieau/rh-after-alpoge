#!/usr/bin/env python3
"""Write the data of the book's Tau Ceti Explorer view, site/explorer/rh.graph.json (run from anywhere).

Usage: python3 tools/explorer_data.py [--out PATH]

tools/render.py runs this on every pass. It reads manuscript/ (in the order of book.json), tags.json
and runtime/decls.sqlite, and writes one JSON file for explorer/index.html:

- chapters and sections, with their numbers, titles and tags;
- one node per labelled statement (theorem, proposition, lemma, corollary, definition, situation,
  remark, ...): its label, tag, kind, number, a short title (the optional argument, or the first
  words of the statement), chapter, section, the texts of the open steps in it, a link to its tag
  page and a link to each Lean declaration it cites, at the line that runtime/decls.sqlite gives;
- relations: the \\ref and \\eqref citations that a statement and its proof make of other
  statements. They are the book's citations, not the Lean's dependency graph.

The manuscript is edited while this runs. What cannot be parsed is skipped and counted under
"skipped", and the counts are printed; nothing in the manuscript stops the file being written. The
file is replaced atomically, so a failed run leaves the previous one in place.
"""
import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import lean_source

BOOK = Path(__file__).resolve().parent.parent
MANUSCRIPT = BOOK / "manuscript"
SRC = BOOK / "runtime" / "source" / "lean" / "src"
DECLS = BOOK / "runtime" / "decls.sqlite"
SOURCE_LINKS = BOOK / "runtime" / "evidence" / "source-links.json"
SITE = BOOK / "site"
OUT = SITE / "explorer" / "rh.graph.json"

# The theorem-like environments of tools/prepare_manuscript.py. They share one counter, numbered
# chapter.section.n, as in the built book.
ENVS = ["theorem", "proposition", "lemma", "corollary", "definition", "situation", "remark",
        "example", "conjecture", "notation"]
TOKEN = re.compile(r"\\(chapter|section|subsection)(\*?)\s*\{|\\begin\{(" + "|".join(ENVS) + r")\}|\\openstep\{")
LABEL = re.compile(r"\\label\{([^}]+)\}")
LEAN = re.compile(r"\\leanref\{([^}]+)\}\{([^}]+)\}")
REF = re.compile(r"\\(?:eq)?ref\{([^}]+)\}")
LEGACY_OPEN = re.compile(r"(?m)^[ \t]*%[ \t]*OPEN:.*")
TITLE_WORDS, TITLE_CHARS = 12, 90


def load(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def blank_comments(text):
    """The text with every comment replaced by spaces, so that positions stay those of the file."""
    return re.sub(r"(?m)(?<!\\)%.*$", lambda m: " " * len(m[0]), text)


def group(text, i, open_="{", close="}"):
    """The end (exclusive) of the group that opens at text[i], or -1 if it never closes."""
    depth = 0
    for j in range(i, len(text)):
        c = text[j]
        if j > i and text[j - 1] == "\\":
            continue
        if c == open_:
            depth += 1
        elif c == close:
            depth -= 1
            if depth == 0:
                return j + 1
    return -1


def optional(text, i):
    """(argument, end) of an optional argument [...] at text[i:], skipping whitespace, or (None, i)."""
    j = i
    while j < len(text) and text[j] in " \t\n":
        j += 1
    if j >= len(text) or text[j] != "[":
        return None, i
    depth, k = 0, j
    while k < len(text):
        c = text[k]
        if c == "{":
            end = group(text, k)
            if end < 0:
                return None, i
            k = end
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return text[j + 1:k], k + 1
        k += 1
    return None, i


def environment_end(text, start, env):
    """The end of the \\end{env} that closes the environment opening at start, or -1."""
    begin, end, depth, i = "\\begin{" + env + "}", "\\end{" + env + "}", 0, start
    while True:
        b, e = text.find(begin, i), text.find(end, i)
        if e < 0:
            return -1
        if 0 <= b < e:
            depth, i = depth + 1, b + len(begin)
        else:
            depth, i = depth - 1, e + len(end)
            if depth == 0:
                return i


def skip_leanrefs(text, i):
    """Past the whitespace and \\leanref lines that follow text[:i]."""
    while True:
        m = re.compile(r"\s*\\leanref\{[^}]+\}\{[^}]+\}").match(text, i)
        if not m:
            return i
        i = m.end()


# ---------------------------------------------------------------- plain text

GREEK = ("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi pi rho sigma tau "
         "upsilon phi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega").split()
SYMBOLS = dict(zip(GREEK, "αβγδϵζηθικλμνξπρστυϕχψωΓΔΘΛΞΠΣΥΦΨΩ"))
SYMBOLS.update({
    "varepsilon": "ε", "vartheta": "ϑ", "varphi": "φ", "varpi": "ϖ", "varrho": "ϱ", "varsigma": "ς",
    "leq": "≤", "le": "≤", "leqslant": "≤", "geq": "≥", "ge": "≥", "geqslant": "≥", "neq": "≠",
    "ne": "≠", "in": "∈", "notin": "∉", "ni": "∋", "subset": "⊂", "subseteq": "⊆", "supset": "⊃",
    "supseteq": "⊇", "to": "→", "rightarrow": "→", "longrightarrow": "⟶", "leftarrow": "←",
    "mapsto": "↦", "hookrightarrow": "↪", "Rightarrow": "⇒", "implies": "⇒", "iff": "⟺",
    "times": "×", "cdot": "·", "infty": "∞", "ell": "ℓ", "otimes": "⊗", "oplus": "⊕",
    "bigoplus": "⊕", "bigotimes": "⊗", "cong": "≅", "simeq": "≃", "sim": "∼", "approx": "≈",
    "equiv": "≡", "ll": "≪", "gg": "≫", "ldots": "…", "cdots": "⋯", "dots": "…", "partial": "∂",
    "nabla": "∇", "forall": "∀", "exists": "∃", "cap": "∩", "cup": "∪", "bigcap": "⋂",
    "bigcup": "⋃", "setminus": "∖", "emptyset": "∅", "varnothing": "∅", "circ": "∘", "pm": "±",
    "mp": "∓", "langle": "⟨", "rangle": "⟩", "mid": "|", "lvert": "|", "rvert": "|", "vert": "|",
    "lVert": "‖", "rVert": "‖", "Vert": "‖", "prime": "′", "sum": "Σ", "prod": "Π", "int": "∫",
    "sqrt": "√", "wedge": "∧", "vee": "∨", "neg": "¬", "lfloor": "⌊", "rfloor": "⌋",
    "lceil": "⌈", "rceil": "⌉", "colon": ":", "quad": " ", "qquad": " ", "S": "§",
    "aleph": "ℵ", "hbar": "ℏ", "Re": "Re", "Im": "Im", "deg": "deg", "log": "log", "exp": "exp",
    "det": "det", "dim": "dim", "max": "max", "min": "min", "sup": "sup", "inf": "inf",
    "lim": "lim", "ker": "ker", "gcd": "gcd", "mod": "mod", "bmod": "mod", "pmod": "mod",
    "flat": "♭", "sharp": "♯", "natural": "♮", "star": "⋆", "ast": "∗", "dagger": "†", "perp": "⊥",
    "triangleleft": "◁", "trianglelefteq": "⊴", "lbrace": "\x01", "rbrace": "\x02",
})
BLACKBOARD = {"Z": "ℤ", "Q": "ℚ", "R": "ℝ", "C": "ℂ", "N": "ℕ", "F": "𝔽", "A": "𝔸", "P": "ℙ"}
# Macros whose argument is kept as it is; their own name says only how it is set.
FONTS = ("emph|textbf|textit|textrm|textsf|texttt|text|mathrm|mathit|mathsf|mathtt|mathbf|mathbb|"
         "mathcal|mathscr|mathfrak|boldsymbol|operatorname\\*?|mbox|hbox|underline|bm")
STRUCTURE = re.compile(r"\\(?:label\{[^}]*\}|leanref\{[^}]*\}\{[^}]*\}|(?:begin|end)\{[^}]*\})")
SIZING = re.compile(r"\\(?:left|right|big|Big|bigg|Bigg|bigl|bigr|Bigl|Bigr|biggl|biggr|displaystyle|"
                    r"textstyle|limits|nolimits|noindent|par|medskip|smallskip|bigskip|item|"
                    r"[,;:! ]|quad|qquad)(?![a-zA-Z])")


def plain(tex, numbers):
    """A readable plain-text form of a little TeX: references become numbers, Greek and common
    symbols become Unicode, font macros keep their argument. Not a TeX renderer."""
    s = tex.replace("\\{", "\x01").replace("\\}", "\x02")  # literal braces survive the clean-up
    s = REF.sub(lambda m: numbers.get(m[1], m[1]), s)
    s = re.sub(r"\\cite(?:\[([^\]]*)\])?\{([^}]*)\}",
               lambda m: "[" + m[2].replace(",", ", ") + (", " + m[1] if m[1] else "") + "]", s)
    s = re.sub(r"\\openstep\{", "{", s)
    s = SIZING.sub(" ", STRUCTURE.sub(" ", s))
    s = re.sub(r"\\(?:mathbf|mathbb)\s*\{?([A-Z])\}?(?![a-zA-Z])", lambda m: BLACKBOARD.get(m[1], m[1]), s)
    for _ in range(4):  # nested arguments, innermost first
        s = re.sub(r"\\(?:" + FONTS + r")\s*\{([^{}]*)\}", r"\1", s)
        s = re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}",
                   lambda m: (m[1] if len(m[1]) <= 1 else "(" + m[1] + ")") + "/" +
                   (m[2] if len(m[2]) <= 1 else "(" + m[2] + ")"), s)
        s = re.sub(r"\\(?:bar|overline)\s*\{([^{}]*)\}", lambda m: m[1] + "\u0304", s)
        s = re.sub(r"\\(?:hat|widehat)\s*\{([^{}]*)\}", lambda m: m[1] + "\u0302", s)
        s = re.sub(r"\\(?:tilde|widetilde)\s*\{([^{}]*)\}", lambda m: m[1] + "\u0303", s)
    s = re.sub(r"\\(?:" + FONTS + r")\s+", "", s)
    s = re.sub(r"\\([a-zA-Z]+)(?![a-zA-Z])", lambda m: SYMBOLS.get(m[1], m[0]), s)
    s = re.sub(r"\\(?:bar|overline)\s*([^\s\\{}])", lambda m: m[1] + "\u0304", s)
    s = re.sub(r"([_^])\{([^{}]*)\}", lambda m: m[1] + (m[2] if len(m[2]) <= 1 else "(" + m[2] + ")"), s)
    s = re.sub(r"\\\\|~", " ", s)
    s = re.sub(r"\\([a-zA-Z]+)", r"\1", s)
    s = re.sub(r"(?<!\\)[{}$]", "", s).replace("\x01", "{").replace("\x02", "}").replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "")
    s = s.replace("---", "—").replace("--", "–").replace("``", "“").replace("''", "”")
    s = re.sub(r"\\(?=\W)", "", s)
    return " ".join(s.split())


def short_title(argument, body, numbers):
    if argument and argument.strip():
        return plain(argument, numbers)
    words = plain(re.sub(r"\\openstep\{", "{", body), numbers).split()
    text = " ".join(words[:TITLE_WORDS])
    if len(text) > TITLE_CHARS:
        text = text[:TITLE_CHARS].rsplit(" ", 1)[0]
    return text + ("…" if text != " ".join(words) else "")


# ---------------------------------------------------------------- Lean lines


class Decls:
    """Lines of declarations: runtime/decls.sqlite, then the last build's resolved links."""

    def __init__(self):
        self.db = sqlite3.connect(f"file:{DECLS}?mode=ro", uri=True) if DECLS.exists() else None
        self.built = {(r.get("path"), r.get("requested_declaration")): r
                      for r in load(SOURCE_LINKS, []) if isinstance(r, dict)}
        self.files = {}

    def has_file(self, path):
        if path not in self.files:
            # Without the archive (another machine), trust the path and let the index decide.
            self.files[path] = (path.endswith(".lean") and ".." not in Path(path).parts
                                and not path.startswith("/") and (not SRC.is_dir() or (SRC / path).is_file()))
        return self.files[path]

    def resolve(self, path, name):
        """(line, how): how the line was found, or (None, why not)."""
        if not self.has_file(path):
            return None, "file not in the archive"
        if self.db is not None:
            try:
                rows = self.db.execute("select line from decls where file = ? and name = ? order by line",
                                       (path, name)).fetchall()
                if rows:
                    return rows[0][0], "declaration"
                last = name.rsplit(".", 1)[-1]
                rows = [r for r in self.db.execute("select name, line from decls where file = ? and last = ?",
                                                   (path, last))
                        if r[0].endswith("." + name) or name.endswith("." + r[0])]
                if len(rows) == 1:
                    return rows[0][1], "declaration"
                if "." in name:
                    rows = self.db.execute("select line from decls where file = ? and name = ? order by line",
                                           (path, name.rsplit(".", 1)[0])).fetchall()
                    if rows:
                        return rows[0][0], "generated by its parent"
            except sqlite3.Error:
                pass
        built = self.built.get((path, name))
        if built and isinstance(built.get("line"), int):
            return built["line"], "generated (from the last build)"
        return None, "declaration not found"


# ---------------------------------------------------------------- the manuscript


def git_head():
    r = subprocess.run(["git", "-C", str(BOOK), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or None


def scan_chapter(text):
    """Chapter and sections, statements and open steps of one chapter file, in order of position."""
    blank = blank_comments(text)
    events = []
    for m in LEGACY_OPEN.finditer(text):
        events.append(("open", m.start(), m.end(), "Not yet written out in the book.", m[0]))
    i = 0
    while True:
        m = TOKEN.search(blank, i)
        if not m:
            break
        if m[1]:  # \chapter, \section or \subsection
            end = group(blank, m.end() - 1)
            if end < 0:
                events.append(("skip", m.start(), m.end(), "unclosed " + m[1] + " title", None))
                i = m.end()
                continue
            label = re.compile(r"\s*\\label\{([^}]+)\}").match(blank, end)
            events.append((m[1], m.start(), end, blank[m.end():end - 1], (label[1] if label else None, bool(m[2]))))
            i = end
        elif m[3]:  # a statement
            env, start = m[3], m.start()
            argument, body_start = optional(blank, m.end())
            end = environment_end(blank, start, env)
            if end < 0:
                events.append(("skip", start, m.end(), "unclosed " + env, None))
                i = m.end()
                continue
            body = blank[body_start:end - len("\\end{" + env + "}")]
            after = skip_leanrefs(blank, end)
            proof = ""
            p = re.compile(r"\s*\\begin\{proof\}").match(blank, after)
            if p:
                proof_end = environment_end(blank, p.end() - len("\\begin{proof}"), "proof")
                if proof_end > 0:
                    proof = blank[p.end():proof_end - len("\\end{proof}")]
                    after = skip_leanrefs(blank, proof_end)
            events.append(("statement", start, after, env, (argument, body, proof, blank[end:after])))
            # Statements are not nested; the next search starts inside this one only for open steps.
            for o in re.finditer(r"\\openstep\{", blank[start:after]):
                close = group(blank, start + o.end() - 1)
                if close > 0:
                    events.append(("open", start + o.start(), close,
                                   " ".join(blank[start + o.end():close - 1].split()), None))
                else:
                    events.append(("skip", start + o.start(), start + o.end(), "unclosed openstep", None))
            i = after
        else:  # an open step outside any statement
            close = group(blank, m.end() - 1)
            if close > 0:
                events.append(("open", m.start(), close, " ".join(blank[m.end():close - 1].split()), None))
                i = close
            else:
                events.append(("skip", m.start(), m.end(), "unclosed openstep", None))
                i = m.end()
    return sorted(events, key=lambda e: (e[1], e[0] != "statement"))


def build():
    book = load(MANUSCRIPT / "book.json", {})
    tags = load(BOOK / "tags.json", {})
    if not isinstance(tags, dict):
        tags = {}
    skipped = {"chapter files missing or unreadable": [], "statements without a label": 0,
               "statements with several labels": 0, "duplicate labels": [], "unclosed environments or groups": 0,
               "open steps outside a statement": 0}
    chapters, sections, nodes = [], [], []
    numbers = {}
    parsed = []
    # First pass: structure and numbers, so that references can be shown as numbers.
    for entry in book.get("entries", []):
        file = entry.get("file", "")
        try:
            text = (MANUSCRIPT / file).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            skipped["chapter files missing or unreadable"].append(file)
            continue
        cnum = len(chapters) + 1
        chapter_id = "chapter-" + Path(file).stem
        events = scan_chapter(text)
        chapter = {"id": chapter_id, "number": str(cnum), "title": entry.get("title") or Path(file).stem,
                   "file": file, "tag": tags.get(chapter_id)}
        chapters.append(chapter)
        numbers[chapter_id] = str(cnum)
        snum, counter, section = 0, 0, None
        items = []
        for kind, start, end, a, b in events:
            if kind == "chapter":
                label = b[0]
                if label and label != chapter_id:
                    numbers[label] = str(cnum)
                if a.strip():
                    chapter["tex_title"] = a
            elif kind == "section":
                label, starred = b
                if not starred:
                    snum, counter = snum + 1, 0
                number = f"{cnum}.{snum}" if not starred else None
                section = {"id": label or f"view:section/{chapter_id}/{len(sections)}", "label": label,
                           "number": number, "tex_title": a, "chapter": chapter_id, "tag": tags.get(label)}
                sections.append(section)
                if label and number:
                    numbers[label] = number
            elif kind == "subsection":
                # Statements share the subsection counter, as in the book (Lemma 13.9.4 may follow
                # Subsection 13.9.3); subsections are not nodes of the explorer.
                label, starred = b
                if not starred:
                    counter += 1
                    if label:
                        numbers[label] = f"{cnum}.{snum}.{counter}"
            elif kind == "statement":
                counter += 1
                argument, body, proof, trailing = b
                labels = LABEL.findall(body)
                number = f"{cnum}.{snum}.{counter}"
                if labels:
                    numbers.setdefault(labels[0], number)
                items.append({"kind": a, "start": start, "end": end, "argument": argument, "body": body,
                              "proof": proof, "trailing": trailing, "labels": labels, "number": number,
                              "section": section})
            elif kind == "open":
                items.append({"open": a, "tex": a, "start": start, "end": end})
            else:
                skipped["unclosed environments or groups"] += 1
        parsed.append((chapter, items))

    for section in sections:
        section["title"] = plain(section.pop("tex_title"), numbers) or section["id"]
    for chapter in chapters:
        chapter.pop("tex_title", None)

    # Second pass: statements, open steps, links and relations.
    decls = Decls()
    by_label, seen = {}, set()
    lean_counts = {}
    for chapter, items in parsed:
        statements = [it for it in items if "kind" in it]
        last = None
        for it in items:
            if "kind" in it:
                last = it
                continue
            owner = next((s for s in statements if s["start"] <= it["start"] < s["end"]), None)
            if owner is None:
                skipped["open steps outside a statement"] += 1
                owner = last  # as on the status page: the statement before it
            if owner is not None:
                owner.setdefault("opens", []).append(it["tex"])
        for it in statements:
            if not it["labels"]:
                skipped["statements without a label"] += 1
                continue
            if len(it["labels"]) > 1:
                skipped["statements with several labels"] += 1
            label = it["labels"][0]
            if label in seen:
                skipped["duplicate labels"].append(label)
                continue
            seen.add(label)
            section = it["section"]
            tag = tags.get(label)
            links = []
            if tag:
                links.append({"type": "tag", "url": f"../book/tag/{tag}.html",
                              "built": (SITE / "book" / "tag" / f"{tag}.html").exists()})
            for path, name in dict.fromkeys(LEAN.findall(it["body"] + it["trailing"])):
                line, how = decls.resolve(path, name)
                lean_counts[how] = lean_counts.get(how, 0) + 1
                link = {"type": "lean", "file": path, "decl": name, "line": line, "how": how}
                if line:
                    link["url"] = lean_source.url(path, line)
                elif how != "file not in the archive":
                    link["url"] = lean_source.url(path)
                links.append(link)
            node = {
                "label": label, "tag": tag, "kind": it["kind"], "number": it["number"],
                "title": short_title(it["argument"], it["body"], numbers),
                "named": bool(it["argument"] and it["argument"].strip()),
                "chapter": chapter["id"], "section": section["id"] if section else None,
                "open_steps": [{"text": plain(t, numbers), "tex": t} for t in it.get("opens", [])],
                "has_proof": bool(it["proof"].strip()),
                "links": links,
                "_refs": [("statement", r) for r in REF.findall(it["body"])] +
                         [("proof", r) for r in REF.findall(it["proof"])],
            }
            nodes.append(node)
            by_label[label] = node

    relations, rel_index = [], {}
    ref_counts = {"to statements": 0, "to chapters or sections": 0, "to unknown labels": 0, "to itself": 0}
    structural = {c["id"] for c in chapters} | {s["label"] for s in sections if s["label"]}
    for node in nodes:
        for where, target in node.pop("_refs"):
            if target == node["label"]:
                ref_counts["to itself"] += 1
            elif target in by_label:
                ref_counts["to statements"] += 1
                key = (node["label"], target)
                if key not in rel_index:
                    rel_index[key] = {"source": node["label"], "target": target, "type": "cites", "in": []}
                    relations.append(rel_index[key])
                if where not in rel_index[key]["in"]:
                    rel_index[key]["in"].append(where)
            elif target in structural or target in numbers:
                ref_counts["to chapters or sections"] += 1
            else:
                ref_counts["to unknown labels"] += 1

    for s in sections:
        if s["tag"]:
            s["url"] = f"../book/tag/{s['tag']}.html"
    for c in chapters:
        if c["tag"]:
            c["url"] = f"../book/tag/{c['tag']}.html"
    open_total = sum(len(n["open_steps"]) for n in nodes)
    counts = {
        "chapters": len(chapters), "sections": len(sections), "statements": len(nodes),
        "statements_by_kind": {k: sum(n["kind"] == k for n in nodes) for k in ENVS if any(n["kind"] == k for n in nodes)},
        "statements_with_open_steps": sum(bool(n["open_steps"]) for n in nodes),
        "open_steps": open_total,
        "untagged_statements": sum(not n["tag"] for n in nodes),
        "tag_links": sum(l["type"] == "tag" for n in nodes for l in n["links"]),
        "lean_links": sum(l["type"] == "lean" for n in nodes for l in n["links"]),
        "lean_links_by_resolution": lean_counts,
        "relations": len(relations),
        "references": ref_counts,
    }
    skipped["duplicate labels"] = sorted(set(skipped["duplicate labels"]))
    return {
        "schema": "rh.explorer.graph.v1",
        "title": book.get("title", ""),
        "generated": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": {"manuscript": "manuscript/*.tex in the order of manuscript/book.json", "commit": git_head(),
                   "declarations": "runtime/decls.sqlite"},
        "semantics": {
            "relations": ("A relation records that a statement or its proof cites another statement with \\ref"
                          " or \\eqref. These are the book's citations. They are not the dependency graph of"
                          " the Lean proof, which is not available until the cluster build's dependency data"
                          " exists."),
            "open_steps": "The \\openstep marks of the manuscript: steps the book does not yet carry out.",
            "numbers": "Computed from the manuscript as the book numbers statements (chapter.section.n).",
        },
        "counts": counts,
        "skipped": skipped,
        "chapters": chapters,
        "sections": [{k: v for k, v in s.items() if k != "label"} for s in sections],
        "nodes": nodes,
        "relations": relations,
    }


def write_atomically(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".rh.graph.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    data = build()
    write_atomically(args.out, data)
    c, s = data["counts"], data["skipped"]
    skips = {k: (len(v) if isinstance(v, list) else v) for k, v in s.items()}
    print(f"explorer: {c['chapters']} chapters, {c['sections']} sections, {c['statements']} statements"
          f" ({c['statements_with_open_steps']} with {c['open_steps']} open steps), {c['tag_links']} tag links,"
          f" {c['lean_links']} Lean links, {c['relations']} relations; skipped {json.dumps(skips)}"
          f" -> {args.out}")


if __name__ == "__main__":
    sys.exit(main())
