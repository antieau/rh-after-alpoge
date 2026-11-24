"""Check the manuscript's cross-references (run from the book directory).

Usage: python3 tools/check_refs.py [--fix]

Prints one line per problem, `file:line: problem`: a \\ref or \\eqref to a label that no file
defines, a label defined twice, a reference whose word (Theorem, Definition, Chapter, ...) does
not match the kind of what it names, an environment that is not closed, or closed twice (a proof
missing its \\end{proof} swallows the statements after it in the build), or an unbraced [ in a
statement's title, such as [Name \\cite[p.~1]{key}], which stops XeLaTeX. With --fix, a wrong
word in a singular reference is replaced by the right one. Exit status is 1 if any problem
remains.
"""
import re
import sys
from pathlib import Path

BOOK = Path(__file__).resolve().parent.parent
MANUSCRIPT = BOOK / "manuscript"
KINDS = {
    "chapter": "Chapter", "section": "Section", "subsection": "Section", "theorem": "Theorem", "lemma": "Lemma",
    "proposition": "Proposition", "corollary": "Corollary", "definition": "Definition",
    "remark": "Remark", "example": "Example", "situation": "Situation", "conjecture": "Conjecture",
    "notation": "Notation", "equation": "equation", "align": "equation", "gather": "equation",
}
WORDS = "|".join(sorted({w for w in KINDS.values() if w != "equation"}))
REF = re.compile(r"\b(" + WORDS + r")(s?)(~|\s+)\\ref\{([^}]*)\}")


def strip(line):
    return re.sub(r"(?<!\\)%.*", "", line)


def labels():
    """label -> (kind, file, line)"""
    out, dupes = {}, []
    for path in sorted(MANUSCRIPT.glob("*.tex")):
        kind = None
        for i, line in enumerate(path.read_text().split("\n"), 1):
            line = strip(line)
            for m in re.finditer(r"\\(chapter|section|subsection)\*?\{|\\begin\{(\w+)\*?\}|\\label\{([^}]*)\}", line):
                if m.group(1):
                    kind = m.group(1)
                elif m.group(2):
                    if m.group(2) in KINDS:
                        kind = m.group(2)
                elif m.group(3):
                    if m.group(3) in out:
                        dupes.append(f"{path.name}:{i}: label {m.group(3)} also defined at "
                                     f"{out[m.group(3)][1]}:{out[m.group(3)][2]}")
                    out[m.group(3)] = (kind, path.name, i)
    return out, dupes


def environments():
    """Each \\begin{...} must be closed, in order, by its own \\end{...} in the same file."""
    out = []
    for path in sorted(MANUSCRIPT.glob("*.tex")):
        stack = []
        for i, line in enumerate(path.read_text().split("\n"), 1):
            for m in re.finditer(r"\\(begin|end)\{([^}]*)\}", strip(line)):
                if m.group(1) == "begin":
                    stack.append((m.group(2), i))
                elif stack and stack[-1][0] == m.group(2):
                    stack.pop()
                else:
                    opened = f", but {stack[-1][0]} opened at line {stack[-1][1]} is still open" if stack else ""
                    out.append(f"{path.name}:{i}: \\end{{{m.group(2)}}}{opened or ' closes nothing'}")
                    if stack:
                        stack.pop()
        out += [f"{path.name}:{i}: \\begin{{{env}}} is never closed" for env, i in stack]
    return out


def titles():
    """A [ inside a statement's optional title must be braced, as in [Name {\\cite[...]{key}}]."""
    out = []
    for path in sorted(MANUSCRIPT.glob("*.tex")):
        for i, line in enumerate(path.read_text().split("\n"), 1):
            for m in re.finditer(r"\\begin\{\w+\}\[", strip(line)):
                depth, rest = 0, strip(line)[m.end():]
                for ch in rest:
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                    elif ch == "]" and depth == 0:
                        break
                    elif ch == "[" and depth == 0:
                        out.append(f"{path.name}:{i}: unbraced [ in a statement title; write {{\\cite[...]{{...}}}}")
                        break
    return out


def main(argv):
    fix = "--fix" in argv
    defined, problems = labels()
    problems += environments() + titles()
    for path in sorted(MANUSCRIPT.glob("*.tex")):
        lines = path.read_text().split("\n")
        changed = False
        for i, line in enumerate(lines, 1):
            code = strip(line)
            for m in re.finditer(r"\\(?:eq)?ref\{([^}]*)\}", code):
                if m.group(1) not in defined:
                    problems.append(f"{path.name}:{i}: undefined label {m.group(1)}")
            for m in REF.finditer(code):
                word, plural, label = m.group(1), m.group(2), m.group(4)
                if label not in defined:
                    continue
                right = KINDS.get(defined[label][0])
                if right and right != "equation" and right != word:
                    if fix and not plural:
                        lines[i - 1] = lines[i - 1].replace(m.group(0), right + m.group(0)[len(word):], 1)
                        changed = True
                    else:
                        problems.append(f"{path.name}:{i}: {word}{plural} \\ref{{{label}}} names a {right}")
        if changed:
            path.write_text("\n".join(lines))
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
