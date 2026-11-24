#!/usr/bin/env python3
"""Check the delivered PDF destinations, Lean links and chapter splits, and that the edition holds
the current build's PDFs and no others (run by tools/build.py)."""
import json
import os
from pathlib import Path
from urllib.parse import quote

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SITE = Path(os.environ.get("BOOK_SITE", ROOT / "site/book"))
EVIDENCE = ROOT / "runtime/evidence"
PUBLISHED = "https://rh.antieau.workers.dev"


def main():
    report = json.loads((EVIDENCE / "pdf-report.json").read_text())
    delivered = {p.name for p in SITE.glob("*.pdf")}
    current = {report["file"]} | {chapter["file"] for chapter in report["chapters"]}
    if delivered != current:
        raise SystemExit("The edition's PDFs are not the current build's: extra " + repr(sorted(delivered - current))
                         + ", missing " + repr(sorted(current - delivered)))
    reader = PdfReader(SITE / report["file"])
    active = [line.split(",", 1)[0] for line in (ROOT / "runtime/build/tags.csv").read_text().splitlines() if line]
    missing = set(active) - set(reader.named_destinations)
    if missing:
        raise SystemExit("PDF is missing tag destinations: " + repr(sorted(missing)))
    expected = set()
    for record in json.loads((EVIDENCE / "source-links.json").read_text()):
        path, _, line = record["url"].partition("#")
        expected.add(("" if "://" in path else PUBLISHED) + quote(path, safe="/:") + "#" + line)
    actual = set()
    for page in reader.pages:
        for reference in page.get("/Annots", []):
            action = reference.get_object().get("/A", {})
            if action.get("/S") == "/URI":
                actual.add(str(action.get("/URI")))
    if expected - actual:
        raise SystemExit("PDF is missing Lean links: " + repr(sorted(expected - actual)[:10]))
    for chapter in report["chapters"]:
        split = PdfReader(SITE / chapter["file"])
        if len(split.pages) != chapter["pages"] or not split.pages:
            raise SystemExit("Incorrect chapter PDF: " + chapter["file"])
    print(json.dumps({"book": report["file"], "pages": len(reader.pages), "tag_destinations": len(active),
                      "Lean_URLs": len(expected), "chapter_PDFs": len(report["chapters"])}))


if __name__ == "__main__":
    main()
