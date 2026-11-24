#!/usr/bin/env python3
"""Prepare conventional LaTeX and checked Lean links for Gerby (run by tools/build.py).

Assembles the chapters of manuscript/book.json with their introductions (transitions-*.tex),
correspondence notes (correspondence-*.json) and bibliographies (references-*.bib), checks labels,
references, citations and permanent tags, and resolves every \\leanref against the pinned archive:
the file must be in runtime/source and the declaration in runtime/decls.sqlite, at a line whose
text names it. A declaration that a command or another declaration generates has no line of its
own; it is linked to the declaration that generates it (its parent in the same file) or to the
line of the file that names it, and the build fails only if neither exists.

Writes runtime/build/resolution.tex, references.bib and tags.csv, and runtime/evidence/
statement-map.json and source-links.json.
"""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path

import lean_source

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
BUILD = RUNTIME / "build"
EVIDENCE = RUNTIME / "evidence"
SRC = RUNTIME / "source/lean/src"
DECLS = RUNTIME / "decls.sqlite"
# The publishing script points BOOK_MANUSCRIPT at a copy of the last commit's manuscript, so that the
# book never catches agents half way through an edit.
MANUSCRIPT = Path(os.environ.get("BOOK_MANUSCRIPT") or ROOT / "manuscript")
LEAN = re.compile(r"\\leanref\{([^}]+)\}\{([^}]+)\}")
LABEL = re.compile(r"\\label\{([^}]+)\}")
REF = re.compile(r"\\(?:eq)?ref\{([^}]+)\}")
CITE = re.compile(r"\\cite(?:\[[^\]]*\])?\{([^}]+)\}")
# \openstep{...} marks, for the reader, a step the book does not yet carry out. An older
# "% OPEN:" comment block that has no \openstep yet is shown with a generic one.
LEGACY_OPEN = re.compile(r"(?m)^[ \t]*%[ \t]*OPEN:.*(?:\n[ \t]*%(?![ \t]*(?:OPEN:|before:)).*)*")


def open_steps(source):
    """(start, end, text) of each \\openstep{...}, with braces nested to any depth."""
    out, i = [], 0
    while (i := source.find("\\openstep{", i)) >= 0:
        depth, j = 0, i + len("\\openstep")
        for j in range(j, len(source)):
            depth += {"{": 1, "}": -1}.get(source[j], 0) if source[j - 1] != "\\" else 0
            if depth == 0:
                break
        out.append((i, j + 1, source[i + len("\\openstep{"):j]))
        i = j + 1
    return out


def mark_open(source):
    source = LEGACY_OPEN.sub(lambda m: m[0] + "\n\\openstep{This step is not yet written out in the book.}", source)
    for start, end, text in reversed(open_steps(source)):
        source = source[:start] + "\\par\\noindent\\textbf{Open step.} " + text + "\\par " + source[end:]
    return source


ENVS = "theorem|proposition|lemma|corollary|definition|situation|remark|example|conjecture|notation"
LEANREFS = r"((?:\s*\\leanref\{[^}]+\}\{[^}]+\})*)"
# A statement, then its Lean lines and its proof in either order.
ITEM = re.compile(
    r"\\begin\{(" + ENVS + r")\}(.*?)\\end\{\1\}" + LEANREFS
    + r"(\s*\\begin\{proof\}.*?\\end\{proof\})?" + LEANREFS, re.S)
TAG = re.compile(r"Z[0-9A-Z]{3}")
# Declarations that Lean generates for a structure, inductive type or definition.
AUXILIARY = re.compile(r"mk|rec|recOn|casesOn|brecOn|binductionOn|below|ibelow|noConfusion|noConfusionType|"
                       r"ext|ext_iff|inj|injEq|sizeOf_spec|eq_def|eq_\d+|induct|mutual_induct")
PREAMBLE = r"""\documentclass{report}
\usepackage{amssymb,amsmath,amsthm,hyperref}
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
\begin{document}
"""


def strip_comments(text):
    return re.sub(r"(?m)(?<!\\)%.*$", "", text)


def manifest():
    return json.loads((MANUSCRIPT / "book.json").read_text())


def chapters():
    """The chapter files in book order, each checked to open with its chapter heading."""
    out = []
    for entry in manifest()["entries"]:
        text = (MANUSCRIPT / entry["file"]).read_text()
        chapter_id = Path(entry["file"]).stem
        head = re.match(r"\s*\\chapter\{(?:[^{}]|\{[^{}]*\})*\}\s*\\label\{([^}]+)\}", strip_comments(text))
        if not head or head[1] != "chapter-" + chapter_id:
            raise ValueError(entry["file"] + " must start with \\chapter{...}\\label{chapter-" + chapter_id + "}")
        out.append((chapter_id, text))
    return out


def document_labels():
    """Every label of the assembled manuscript, in order (the labels that need tags)."""
    return LABEL.findall(strip_comments("\n\n".join(text for _, text in chapters())))


def read_register():
    path = ROOT / "tags.json"
    register = json.loads(path.read_text()) if path.exists() else {}
    tags = list(register.values())
    bad = [t for t in tags if not TAG.fullmatch(t)]
    if bad:
        raise ValueError("Tags must be Z followed by three base-36 digits: " + str(bad[:10]))
    duplicates = [t for t, n in Counter(tags).items() if n > 1]
    if duplicates:
        raise ValueError("Tags assigned twice in tags.json: " + str(duplicates))
    return register


def committed_register():
    """tags.json as last committed, or {} outside Git."""
    try:
        text = subprocess.run(["git", "show", "HEAD:./tags.json"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout
        return json.loads(text)
    except (subprocess.CalledProcessError, ValueError, OSError):
        return {}


def transitions():
    out = {}
    for path in sorted(MANUSCRIPT.glob("transitions*.tex")):
        for label, text in re.findall(
                r"(?ms)^% before: ([\w:-]+)\s*\n(.*?)(?=^% before: |\Z)", path.read_text()):
            if label in out:
                raise ValueError("Duplicate transition: " + label + " (" + path.name + ")")
            out[label] = text
    return out


def correspondence():
    out = {}
    for path in sorted(MANUSCRIPT.glob("correspondence*.json")):
        for label, note in json.loads(path.read_text()).items():
            if label in out and out[label] != note:
                raise ValueError("Two correspondence notes for " + label + " (" + path.name + ")")
            out[label] = note
    return out


def bib_entries(text):
    """(key, source) for each entry of a BibTeX file, by brace matching."""
    position = 0
    head = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")
    while True:
        m = head.search(text, position)
        if not m:
            return
        depth, end = 0, None
        for i in range(text.index("{", m.start()), len(text)):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            if depth == 0:
                end = i + 1
                break
        if end is None:
            raise ValueError("Unbalanced BibTeX entry " + m[2])
        if m[1].lower() not in ("comment", "preamble", "string"):
            yield m[2], text[m.start():end]
        position = end


def normal(entry):
    return " ".join(re.sub(r"^@\w+", lambda m: m[0].lower(), entry).split())


def bibliography(order):
    """One bibliography from the chapters' files. A key defined twice keeps its fuller entry."""
    chosen, conflicts = {}, {}
    paths = [MANUSCRIPT / ("references-" + chapter_id + ".bib") for chapter_id in order]
    paths += [p for p in sorted(MANUSCRIPT.glob("references*.bib")) if p not in paths]
    for path in paths:
        if not path.exists():
            continue
        for key, source in bib_entries(path.read_text()):
            fields = len(re.findall(r"(?m)^\s*\w+\s*=", source))
            if key in chosen:
                if normal(source) != normal(chosen[key][0]):
                    conflicts.setdefault(key, [chosen[key][2]]).append(path.name)
                if fields <= chosen[key][1]:
                    continue
            chosen[key] = (source, fields, path.name)
    text = "\n\n".join(source for source, _, _ in chosen.values()) + "\n"
    return text, set(chosen), conflicts


def tex_escape(s):
    return "".join({"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&",
                    "#": r"\#", "%": r"\%", "_": r"\_", "^": r"\^{}", "~": r"\~{}"}.get(c, c) for c in s)


class Archive:
    """The pinned Lean sources and their declaration index."""

    def __init__(self):
        lock = json.loads((ROOT / "toolchain.lock.json").read_text())
        complete = RUNTIME / "source/.complete"
        if not complete.exists() or complete.read_text().strip() != lock["lean"]["archive_sha256"]:
            raise ValueError("runtime/source is not the pinned archive; run tools/bootstrap.py")
        self.sha256 = lock["lean"]["archive_sha256"]
        self.db = sqlite3.connect(DECLS)
        self.files = {}

    def lines(self, path):
        if path not in self.files:
            raw = (SRC / path).read_bytes()
            self.files[path] = (hashlib.sha256(raw).hexdigest(),
                                raw.decode("utf-8", errors="replace").split("\n"))
        return self.files[path]

    def resolve(self, path, name):
        parts = Path(path).parts
        if (not path.endswith(".lean") or ".." in parts or path.startswith("/")
                or not (SRC / path).is_file()):
            raise LookupError("Not a file of the pinned archive: " + path)
        digest, lines = self.lines(path)
        last = name.rsplit(".", 1)[-1]
        rows = self.db.execute("select name, kind, line from decls where file = ? and name = ?",
                               (path, name)).fetchall()
        if not rows:
            rows = [r for r in self.db.execute(
                "select name, kind, line from decls where file = ? and last = ?", (path, last))
                if r[0].endswith("." + name) or name.endswith("." + r[0])]
        record = {"path": path, "requested_declaration": name, "sha256": digest}
        if len(rows) > 1:
            raise LookupError("Ambiguous declaration: " + path + " : " + name)
        if rows:
            full, kind, line = rows[0]
            if last.strip("«»") not in lines[line - 1]:
                raise LookupError("Declaration index disagrees with the source: " + path + ":" + str(line))
            return dict(record, qualified_declaration=full, kind=kind, line=line, generated=False)
        # Generated by another declaration of the file: a field or constructor named in its
        # parent's text, an auxiliary of the parent (mk, rec, ext, eq_def, ...), or a lemma that
        # @[simps] makes from a sibling.
        word = re.compile(r"(?<![\w.'])" + re.escape(last) + r"(?![\w'])")
        parent = name.rsplit(".", 1)[0] if "." in name else ""
        rows = self.db.execute("select name, kind, line, end_line from decls where file = ? and name = ?",
                               (path, parent)).fetchall()
        if len(rows) == 1:
            full, kind, line, end = rows[0]
            if AUXILIARY.fullmatch(last) or any(word.search(text) for text in lines[line - 1:end]):
                return dict(record, qualified_declaration=name, kind="generated by " + kind,
                            generated_by=full, line=line, generated=True)
        prefix = parent + "." if parent else ""
        for full, kind, line in self.db.execute(
                "select name, kind, line from decls where name >= ? and name < ? and file = ?",
                (prefix, prefix + "\U0010ffff", path)).fetchall():
            base = full.rsplit(".", 1)[-1]
            if (full == prefix + base and last.startswith(base + "_")
                    and any("simps" in text for text in lines[max(0, line - 3):line])):
                return dict(record, qualified_declaration=name, kind="generated by @[simps] " + kind,
                            generated_by=full, line=line, generated=True)
        # Generated by a command that names it.
        for number, text in enumerate(lines, 1):
            if word.search(text):
                return dict(record, qualified_declaration=name, kind="generated by a command",
                            generated_by=text.strip()[:200], line=number, generated=True)
        raise LookupError("No declaration " + name + " in " + path)


def main():
    book = manifest()
    parts = chapters()
    order = [chapter_id for chapter_id, _ in parts]
    source = "\n\n".join(text for _, text in parts)
    intro = transitions()
    initial_labels = set(LABEL.findall(strip_comments(source)))
    unknown = sorted(set(intro) - initial_labels)
    if unknown:
        raise ValueError("Transitions for unknown labels: " + str(unknown))

    def introduce_statement(m):
        label = LABEL.findall(m[2])[0] if LABEL.findall(m[2]) else None
        text = strip_comments(intro.get(label, "")).strip() if label else ""
        if not text:
            return m[0]
        introductions = "\n\n".join(
            r"\hypertarget{context-" + label + "}{\n" + paragraph + "\n}"
            for paragraph in re.split(r"\n\s*\n", text))
        return introductions + "\n\n" + m[0]
    obligations = [line.split("OPEN:", 1)[1].strip() for line in source.splitlines()
                   if re.match(r"\s*%\s*OPEN:", line)]
    obligations += [" ".join(t.split()) for _, _, t in open_steps(strip_comments(source))]
    source = mark_open(ITEM.sub(introduce_statement, source))
    clean = strip_comments(source)
    # plasTeX defines \imath and \jmath last as math accents, which take an argument: in $\jmath$
    # the closing $ is taken, and the rest of the statement is lost. An empty argument keeps the
    # symbol, and TeX and MathJax read \jmath{} as \jmath.
    clean = re.sub(r"\\([ij]math)(?![A-Za-z])(?!\{\})", r"\\\1{}", clean)
    labels = LABEL.findall(clean)
    duplicates = [k for k, v in Counter(labels).items() if v > 1]
    if duplicates:
        raise ValueError("Duplicate labels: " + str(duplicates))
    missing_refs = sorted(set(REF.findall(clean)) - set(labels))
    if missing_refs:
        raise ValueError("Unresolved internal references: " + str(missing_refs))

    bib_text, bib_keys, bib_conflicts = bibliography(order)
    cited = {k.strip() for group in CITE.findall(clean) for k in group.split(",")}
    if cited - bib_keys:
        raise ValueError("Citations without bibliography entries: " + str(sorted(cited - bib_keys)))

    register = read_register()
    untagged = [label for label in labels if label not in register]
    if untagged:
        raise ValueError(str(len(untagged)) + " labels have no permanent tag, for example "
                         + ", ".join(untagged[:5]) + ". Run python3 tools/assign_tags.py first.")
    lost = {tag for tag in committed_register().values()} - set(register.values())
    if lost:
        raise ValueError("Tags in the committed tags.json are missing now: " + str(sorted(lost)))
    BUILD.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (BUILD / "tags.csv").write_text("".join(register[label] + "," + label + "\n" for label in labels))

    archive = Archive()
    resolved, errors = {}, []
    for path, name in sorted(set(LEAN.findall(clean))):
        try:
            record = archive.resolve(path, name)
        except LookupError as error:
            errors.append(str(error))
            continue
        record["url"] = lean_source.url(path, record["line"])
        resolved[(path, name)] = record
    if errors:
        (EVIDENCE / "source-errors.json").write_text(json.dumps(errors, indent=2, ensure_ascii=False) + "\n")
        raise ValueError("\n".join(errors))
    (EVIDENCE / "source-errors.json").write_text("[]\n")

    notes = correspondence()
    statements = []

    def collect_and_relocate(m):
        env, body, before, proof, after = m.groups()
        proof, refs = proof or "", (before or "") + (after or "")
        own_labels = LABEL.findall(body)
        if len(own_labels) != 1:
            raise ValueError("Statement must have one label: " + body[:100])
        label = own_labels[0]
        own_lean = LEAN.findall(body + refs)
        statements.append({
            "label": label, "tag": register[label], "kind": env,
            "has_proof": bool(proof),
            "lean_references": [resolved[pair] for pair in dict.fromkeys(own_lean)],
            "local_dependencies": list(dict.fromkeys(REF.findall(proof))),
            "correspondence_note": notes.get(label, ""),
        })
        # Put source links in the statement itself so each Gerby tag page has them.
        body = body.rstrip() + "\n" + refs.strip() + "\n"
        return r"\begin{" + env + "}" + body + r"\end{" + env + "}" + proof

    prepared = ITEM.sub(collect_and_relocate, clean)

    def render_lean(m):
        ref = resolved[m.groups()]
        name = r"\texttt{" + tex_escape(ref["requested_declaration"]) + "}"
        if ref["generated"]:
            name += " (generated)"
        return r"\par\noindent\textit{Lean:} \href{" + ref["url"] + "}{" + name + "}.\n"
    prepared = LEAN.sub(render_lean, prepared)
    if r"\leanref" in prepared:
        raise ValueError("Unexpanded source macros")
    (BUILD / "references.bib").write_text(bib_text)
    (BUILD / "resolution.tex").write_text(PREAMBLE + prepared +
        "\n\\bibliographystyle{alpha}\n\\bibliography{references}\n\\end{document}\n")
    report = {
        "title": book["title"],
        "lean_archive_sha256": archive.sha256,
        "verification_scope": (
            "Source files, declaration locations, document references, citations and Gerby "
            "rendering are checked mechanically. This does not verify equivalence of prose and Lean proofs."),
        "labels": len(labels), "statements": len(statements),
        "statement_introductions": sum(bool(intro.get(s["label"], "").strip()) for s in statements),
        "proofs": sum(s["has_proof"] for s in statements),
        "lean_references": len(LEAN.findall(clean)),
        "unique_lean_references": len(resolved),
        "generated_lean_references": sum(r["generated"] for r in resolved.values()),
        "cited_lean_files": len({p for p, _ in resolved}),
        "bibliography_entries": len(bib_keys),
        "bibliography_conflicts": bib_conflicts,
        "statements_without_introductions": [
            s["label"] for s in statements if not intro.get(s["label"], "").strip()],
        "statements_without_lean_references": [
            s["label"] for s in statements if not s["lean_references"]],
        "assertions_without_proofs": [
            s["label"] for s in statements
            if not s["has_proof"] and s["kind"] not in ["definition", "situation", "remark", "notation"]],
        "open_items": obligations,
        "items": statements,
    }
    (EVIDENCE / "statement-map.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    (EVIDENCE / "source-links.json").write_text(
        json.dumps(list(resolved.values()), indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in report.items()
                      if k not in ["items", "statements_without_lean_references", "assertions_without_proofs",
                                   "statements_without_introductions", "open_items"]},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
