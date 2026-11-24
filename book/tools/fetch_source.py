"""Download Alpöge's Lean archive, check it against source.json and unpack it (run from the book directory).

Usage: python3 tools/fetch_source.py

The parts go into runtime/source-parts and the sources into runtime/source/lean. A part already
present is reused if its SHA-256 matches. Nothing in the archive is built or run.

In the book's public repository the archive's files are already there, unpacked as ../lean beside
the book, at the tag that source.json's "browse" names. Then runtime/source/lean is a link to them
and nothing is downloaded; pass --download to fetch and check the archive anyway.
"""
import hashlib
import json
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

BOOK = Path(__file__).resolve().parent.parent
SOURCE = json.loads((BOOK / "source.json").read_text())
PARTS = BOOK / "runtime" / "source-parts"
OUT = BOOK / "runtime" / "source"
DONE = OUT / ".complete"
CHECKOUT = BOOK.parent / "lean"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(part):
    path = PARTS / part["url"].rsplit("/", 1)[1]
    if path.exists() and sha256(path) == part["sha256"]:
        return path
    for attempt in range(3):
        tmp = path.with_suffix(".tmp")
        # alpo.ge refuses Python's default User-Agent with 403.
        req = urllib.request.Request(part["url"], headers={"User-Agent": "rh-book-fetch/1.0 (Resolution)"})
        with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        if sha256(tmp) == part["sha256"]:
            tmp.rename(path)
            return path
        print(f"{path.name}: digest mismatch, retrying", file=sys.stderr)
    sys.exit(f"{path.name}: digest does not match source.json")


class Joined:
    """The parts read as one file, for tarfile."""

    def __init__(self, paths):
        self.files = [open(p, "rb") for p in paths]

    def read(self, n=-1):
        out = b""
        while self.files and (n < 0 or len(out) < n):
            chunk = self.files[0].read(-1 if n < 0 else n - len(out))
            if not chunk:
                self.files.pop(0).close()
            out += chunk
        return out


def main():
    if DONE.exists() and DONE.read_text().strip() == SOURCE["archive"]["sha256"]:
        print(f"{OUT} is up to date")
        return
    if (CHECKOUT / "lakefile.toml").exists() and "--download" not in sys.argv[1:]:
        if OUT.exists():
            shutil.rmtree(OUT)
        OUT.mkdir(parents=True)
        (OUT / "lean").symlink_to(CHECKOUT)
        DONE.write_text(SOURCE["archive"]["sha256"] + "\n")
        print(f"linked {OUT / 'lean'} to {CHECKOUT}")
        return
    PARTS.mkdir(parents=True, exist_ok=True)
    paths = [fetch(p) for p in SOURCE["archive"]["parts"]]
    h = hashlib.sha256()
    for p in paths:
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    if h.hexdigest() != SOURCE["archive"]["sha256"]:
        sys.exit("the joined archive does not match source.json")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    with tarfile.open(fileobj=Joined(paths), mode="r|gz") as tar:
        tar.extractall(OUT, filter="data")
    DONE.write_text(SOURCE["archive"]["sha256"] + "\n")
    print(f"unpacked into {OUT}")


if __name__ == "__main__":
    main()
