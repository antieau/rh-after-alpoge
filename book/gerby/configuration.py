# Local Gerby configuration for the RH book.
#
# ROOT is runtime/gerby, so that the patched application's ROOT.parent paths (the prepared
# manuscript in build/ and the statement map in evidence/) resolve under runtime/.
import json
from pathlib import Path
BOOK = Path(__file__).resolve().parents[1]
ROOT = BOOK / "runtime" / "gerby"
COMMENTS = str(ROOT / "build/comments.sqlite")
DATABASE = str(ROOT / "build/resolution.sqlite")
UNIT = "section"
DEPTH = 1  # chapter and section pages open their contents one level: sections show their subsections
PATH = str(ROOT / "build/document")
PAUX = str(ROOT / "build/document.paux")
TAGS = str(ROOT / "build/tags")
# The PDFs carry their build time in their names; tools/build_pdf.py records the current names in
# build/pdf.json, and the templates link to them. Before the first PDF build there are none.
PDF_NAMES = (json.loads((ROOT / "build/pdf.json").read_text()) if (ROOT / "build/pdf.json").exists()
             else {"book": "book.pdf", "chapters": {}})
BOOK_PDF = PDF_NAMES["book"]
CHAPTER_PDFS = PDF_NAMES["chapters"]
PDF = str(ROOT / "build/downloads" / BOOK_PDF)
# Read by this book's templates (the about page and the citation page).
BOOK_TITLE = json.loads((BOOK / "manuscript/book.json").read_text())["title"]
LEAN_SOURCE = json.loads((BOOK / "source.json").read_text())
