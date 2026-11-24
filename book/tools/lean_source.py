"""Where a reader follows a \\leanref: the archive's file in the book's public repository.

source.json's "browse" is the folder of the archive's src/ there, at the tag that pins the
archive (lean-<first eight digits of its SHA-256>), so a link names the archive the book was
checked against. Paths are left as they are; a URL's user (the browser, the PDF writer) encodes
them.
"""
import json
from pathlib import Path

BOOK = Path(__file__).resolve().parent.parent
BASE = json.loads((BOOK / "source.json").read_text())["browse"]


def url(path, line=None):
    """The URL of an archive file (a path under src/), at line `line` if given."""
    return BASE + path + ("#L" + str(line) if line else "")
