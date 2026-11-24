#!/usr/bin/env python3
"""Give a permanent tag to each label of the manuscript that has none (run from anywhere).

Usage: python3 tools/assign_tags.py [--dry-run]

tags.json maps labels to four-character base-36 tags, from Z000 on. A new tag is always one past
the largest tag ever issued, so a tag is never reassigned or reused: the entries of labels that
have left the manuscript stay in the register. The build refuses to assign tags itself; run this
after adding labelled chapters, sections or statements, and commit tags.json with them.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_manuscript import ROOT, committed_register, document_labels, read_register  # noqa: E402

DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
FIRST = "Z000"


def number(tag):
    n = 0
    for c in tag:
        n = 36 * n + DIGITS.index(c)
    return n


def tag(n):
    s = ""
    for _ in range(4):
        n, r = divmod(n, 36)
        s = DIGITS[r] + s
    return s


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print the new tags without writing tags.json")
    args = parser.parse_args()
    register = read_register()
    issued = list(register.values()) + list(committed_register().values())
    following = max([number(t) + 1 for t in issued] + [number(FIRST)])
    new = {}
    for label in document_labels():
        if label not in register and label not in new:
            if following > number("ZZZZ"):
                raise SystemExit("The tag space Z000-ZZZZ is exhausted")
            new[label] = tag(following)
            following += 1
    for label, t in new.items():
        print(t, label)
    if new and not args.dry_run:
        register.update(new)
        (ROOT / "tags.json").write_text(json.dumps(register, indent=2) + "\n")
    print(f"{len(new)} new tags; {len(register)} in the register", file=sys.stderr)


if __name__ == "__main__":
    main()
