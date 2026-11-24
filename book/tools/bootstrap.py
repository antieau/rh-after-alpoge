#!/usr/bin/env python3
"""Fetch the pinned renderers and Lean archive, and prepare the build's Python environment.

The renderers are public upstream Gerby commits with the Hironaka book's patches, which reproduce
its private renderer commits, and then this book's overlay patch (titles, about page, contents).
Alpöge's Lean has no Git repository: the pin is the archive digest in source.json, which
tools/fetch_source.py checks, and runtime/decls.sqlite is its declaration index.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
DEPS = RUNTIME / "deps"
PYTHON = RUNTIME / ".venv/bin/python"


def run(*command, cwd=None, **kwargs):
    return subprocess.run(list(map(str, command)), cwd=cwd, check=True, **kwargs)


def git_output(checkout, *args):
    return subprocess.check_output(["git", "-C", str(checkout), *args], text=True).strip()


def checkout(repository, revision, path):
    """Create a cache at one immutable revision; never update a moving branch."""
    if not (path / ".git").exists():
        path.mkdir(parents=True, exist_ok=True)
        run("git", "init", "--quiet", path)
        run("git", "-C", path, "remote", "add", "origin", repository)
    if git_output(path, "remote", "get-url", "origin") != repository:
        raise RuntimeError("Unexpected dependency remote: " + str(path))
    exists = subprocess.run(["git", "-C", str(path), "cat-file", "-e", revision + "^{commit}"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if not exists:
        run("git", "-C", path, "fetch", "--quiet", "--depth=1", "origin", revision)
    if not (path / ".git/HEAD").exists() or subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--verify", "HEAD"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        run("git", "-C", path, "checkout", "--quiet", "--detach", revision)
    if git_output(path, "rev-parse", "HEAD") != revision:
        raise RuntimeError("Dependency cache has a different revision; remove " + str(path))


def check_patch(entry, name):
    if hashlib.sha256((ROOT / entry["patch"]).read_bytes()).hexdigest() != entry["patch_sha256"]:
        raise RuntimeError("Renderer patch checksum mismatch: " + name + " " + entry["patch"])


def sources(lock):
    DEPS.mkdir(parents=True, exist_ok=True)
    for name, entry in lock["renderers"].items():
        path = DEPS / name
        overlay = entry.get("overlay")
        check_patch(entry, name)
        if overlay:
            check_patch(overlay, name)
        checkout(entry["upstream_repository"], entry["upstream_revision"], path)
        # The index records how far the cache has been prepared: upstream, the Hironaka renderer
        # commit's tree, or that tree with this book's overlay.
        if git_output(path, "write-tree") == git_output(path, "rev-parse", "HEAD^{tree}"):
            run("git", "-C", path, "apply", "--index", "--binary", "--whitespace=nowarn", ROOT / entry["patch"])
            if git_output(path, "write-tree") != entry["tree"]:
                raise RuntimeError("Reconstructed renderer tree differs from private commit: " + name)
        if overlay and git_output(path, "write-tree") == entry["tree"]:
            run("git", "-C", path, "apply", "--index", "--binary", "--whitespace=nowarn", ROOT / overlay["patch"])
        expected = overlay["tree"] if overlay else entry["tree"]
        if git_output(path, "write-tree") != expected:
            raise RuntimeError("Renderer cache differs from the pinned tree; remove " + str(path)
                               + " (or refresh the overlay with tools/lock_renderer.py)")
        run("git", "-C", path, "diff", "--exit-code", "--quiet")


def lean_source(lock):
    """The pinned archive, unpacked and indexed. Neither step builds or runs the Lean."""
    source = json.loads((ROOT / lock["lean"]["source"]).read_text())
    if source["archive"]["sha256"] != lock["lean"]["archive_sha256"]:
        raise RuntimeError("source.json and toolchain.lock.json pin different Lean archives")
    complete = RUNTIME / "source/.complete"
    if not complete.exists() or complete.read_text().strip() != lock["lean"]["archive_sha256"]:
        run(sys.executable, ROOT / "tools/fetch_source.py", cwd=ROOT)
    index = RUNTIME / "decls.sqlite"
    if not index.exists() or index.stat().st_mtime < complete.stat().st_mtime:
        run(sys.executable, ROOT / "tools/lean.py", "index", cwd=ROOT)


def main():
    lock = json.loads((ROOT / "toolchain.lock.json").read_text())
    if sys.version_info[:2] != tuple(lock["python_minor"]):
        raise SystemExit("Use Python 3.9 (for example ~/.local/bin/python3.9)")
    sources(lock)
    lean_source(lock)
    requirements = ROOT / "gerby/requirements-lock.txt"
    fingerprint = hashlib.sha256(requirements.read_bytes() +
                                 json.dumps(lock, sort_keys=True).encode()).hexdigest()
    stamp = RUNTIME / ".venv/book-environment.sha256"
    if stamp.exists() and stamp.read_text().strip() == fingerprint:
        return
    if not PYTHON.exists():
        # Through the real interpreter: a venv made through a symlink to a relocatable Python
        # (as uv installs it) cannot find the standard library.
        run(os.path.realpath(sys.executable), "-m", "venv", PYTHON.parent.parent)
    env = dict(os.environ, PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONNOUSERSITE="1")
    run(PYTHON, "-m", "pip", "install", "pip==25.3", "setuptools==80.9.0", "wheel==0.45.1", env=env)
    run(PYTHON, "-m", "pip", "install", "-r", requirements, env=env)
    run(PYTHON, "-m", "pip", "install", "--no-deps", "--no-build-isolation", "-e",
        DEPS / "plastex", "-e", DEPS / "gerby-website", env=env)
    run(PYTHON, "-m", "pip", "check", env=env)
    stamp.write_text(fingerprint + "\n")


if __name__ == "__main__":
    main()
