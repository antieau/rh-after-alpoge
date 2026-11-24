"""Flag the mechanical cases of the rules in STYLE.md (run from the book directory).

Usage: python3 tools/check_style.py [--strict] [FILE.tex ...]

Prints one warning per line, `file:line: rule: text`, for manuscript/*.tex (or the files given).
Warnings listed in tools/style-exceptions.txt (`file<TAB>rule<TAB>fragment<TAB>reason`) are
skipped. Exit status is 0, or 1 with --strict when any warning remains.
"""
import re
import sys
from pathlib import Path

BOOK = Path(__file__).resolve().parent.parent
MANUSCRIPT = BOOK / "manuscript"
EXCEPTIONS = BOOK / "tools" / "style-exceptions.txt"

# (rule, pattern, applies to transitions only)
PATTERNS = [
    ("1-importance", r"\bThis is (?:the|a) (?:step|key|point|heart|crux|ingredient)\b"
                     r"|\bmakes? [^.]{0,60}\b(?:effective|work)\b"
                     r"|\b(?:key|crucial|essential|central) (?:step|point|ingredient|idea|role)\b"
                     r"|\bcrucially\b|\bthe heart of\b", False),
    ("2-pointer", r"\b(?:supplies|provides|fills|gives) the missing\b", False),
    ("4-announce", r"\bWe (?:record|isolate|collect|gather)\b|\bWe now (?:record|turn|state)\b", False),
    ("5-naming", r"\bWe (?:give (?:it|this|them|these) (?:a )?names?|name (?:it|this|these|such|them)"
                 r"|fix (?:this|these|the terms|notation|once))\b"
                 r"|\bso that later statements can refer\b", False),
    ("7-formalization", r"\b(?:formali[sz]ation|formali[sz]ed|formal route|Lean)\b"
                        r"|\binterfaces?\b|\bbookkeeping\b"
                        r"|\b[Tt]he source(?:'s)? (?:does|verifies|first|also|satisfies|uses|compares|separate"
                        r"|order-reduction|statement|construction)\b|\bof the source[.,;)]|\bsource repository\b", False),
    ("8-denial", r"\bnot an assumption\b|\bis not circular\b|\bnot (?:merely|simply) (?:a|an)\b", False),
    ("9-contrast", r"\brather than\b|\bnot just\b|\bnot only\b|\binstead of\b|\bnot merely\b", False),
    # "exactly when" and "exactly one" always mean "if and only if" or an exact value.
    ("10-emphasis", r"\b(?:precisely|exactly)\b(?!\s+(?:when|one|two)\b)", False),
    # Rule 13: a pattern for each rejected name that STYLE.md records.
    ("13-name", r"\bthick sets?\b|\bgood windows?\b|\bparameter \$\\varepsilon\$"
                r"|\blevel of (?:a|the|its) theta datum\b|\bseparated types?\b|\bcondition[~ ]\(U\)", False),
    ("em-dash", r"---|\u2014", False),
]


def blank_comments(text):
    """Replace TeX comments by spaces, keeping offsets and newlines."""
    return re.sub(r"(?m)(?<!\\)%.*$", lambda m: " " * len(m.group(0)), text)


def blank_math(text):
    """Replace math and \\ref-like arguments by spaces, keeping offsets and newlines."""
    def spaces(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    text = re.sub(r"\\\[.*?\\\]|\$\$.*?\$\$|\$[^$]*\$", spaces, text, flags=re.S)
    text = re.sub(r"\\(?:ref|eqref|cite|label|leanref|stacks)\*?(?:\[[^\]]*\])?\{[^}]*\}(?:\{[^}]*\})?",
                  spaces, text)
    return text


def sentence_at(text, pos):
    window = max(0, pos - 2000)
    starts = [m.end() for m in re.finditer(r"[.?!]\s|\n\s*\n", text[window:pos])]
    start = window + starts[-1] if starts else window
    end = re.compile(r"[.?!](?=\s|$)").search(text, pos)
    end = end.end() if end else len(text)
    return " ".join(text[start:end].split())[:160]


def one_sentence_paragraphs(path, raw):
    """Paragraphs of a transitions file that consist of a single sentence."""
    out = []
    offset = 0
    for block in re.split(r"(\n\s*\n|\n(?=% before: ))", raw):
        para = block
        start = offset
        offset += len(block)
        body = "\n".join(l for l in para.splitlines() if not l.lstrip().startswith("%"))
        body = blank_math(body)
        words = " ".join(body.split())
        if not words:
            continue
        sentences = [s for s in re.split(r"(?<=[.?!])\s+(?=[A-Z\\])", words) if s.strip()]
        if len(sentences) == 1:
            line = raw.count("\n", 0, start) + 1 + (len(para) - len(para.lstrip("\n")))
            out.append((line, "6-one-sentence-paragraph", words[:160]))
    return out


def load_exceptions():
    exc = []
    if EXCEPTIONS.exists():
        for line in EXCEPTIONS.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                parts = line.split("\t")
                if len(parts) >= 3:
                    exc.append((parts[0], parts[1], parts[2]))
    return exc


def check(path):
    raw = path.read_text()
    text = blank_math(blank_comments(raw))
    is_transitions = path.name.startswith("transitions")
    warnings = []
    for rule, pattern, transitions_only in PATTERNS:
        if transitions_only and not is_transitions:
            continue
        for m in re.finditer(pattern, text, flags=re.I if rule != "7-formalization" else 0):
            line = raw.count("\n", 0, m.start()) + 1
            warnings.append((line, rule, sentence_at(text, m.start())))
    if is_transitions:
        warnings.extend(one_sentence_paragraphs(path, raw))
    return sorted(set(warnings))


def main(argv):
    strict = "--strict" in argv
    files = [Path(a) for a in argv if not a.startswith("--")] or sorted(MANUSCRIPT.glob("*.tex"))
    exceptions = load_exceptions()
    count = 0
    for path in files:
        path = path.resolve()
        for line, rule, sentence in check(path):
            if any(path.name == f and rule == r and frag in sentence for f, r, frag in exceptions):
                continue
            count += 1
            print(f"{path.relative_to(BOOK)}:{line}: {rule}: {sentence}")
    print(f"{count} warnings", file=sys.stderr)
    return 1 if strict and count else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
