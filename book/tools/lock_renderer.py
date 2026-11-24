#!/usr/bin/env python3
"""Record this book's overlay on a renderer: the change from the Hironaka renderer tree to the cache.

Usage: python3 tools/lock_renderer.py gerby-website

Edit runtime/deps/<name> (prepared by tools/bootstrap.py), then run this. It stages every change
in the cache, writes `git diff` from the pinned Hironaka tree to the staged tree as
gerby/patches/<name>-rh.patch, and records the patch's digest and the staged tree in
toolchain.lock.json. The Hironaka patches themselves are copies; refresh those from the Hironaka
book (lean/hironaka/book/tools/lock_renderer.py), not here.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", choices=["gerby-website", "plastex"])
    args = parser.parse_args()
    lock_path = ROOT / "toolchain.lock.json"
    lock = json.loads(lock_path.read_text())
    entry = lock["renderers"][args.name]
    checkout = ROOT / "runtime/deps" / args.name

    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(checkout), *arguments])

    if git("rev-parse", "HEAD").decode().strip() != entry["upstream_revision"]:
        raise SystemExit("The cache is not at the pinned upstream revision")
    # Python's byte-code caches and pip's metadata are not part of the renderer.
    git("add", "--all", "--", ".", ":(exclude,glob)**/__pycache__/**", ":(exclude,glob)**/*.egg-info/**")
    tree = git("write-tree").decode().strip()
    patch = git("diff", "--binary", "--full-index", entry["tree"], tree)
    relative = "gerby/patches/" + args.name + "-rh.patch"
    if not patch:
        (ROOT / relative).unlink(missing_ok=True)
        entry.pop("overlay", None)
    else:
        (ROOT / relative).write_bytes(patch)
        entry["overlay"] = {"patch": relative, "tree": tree,
                            "patch_sha256": hashlib.sha256(patch).hexdigest()}
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    print(args.name, tree)


if __name__ == "__main__":
    main()
