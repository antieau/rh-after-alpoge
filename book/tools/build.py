#!/usr/bin/env python3
"""Build the Gerby book into site/book/, without serving or publishing it.

Usage: python3.9 tools/build.py [--engine xelatex] | --clean

Steps: bootstrap (renderers, Lean archive and index, Python environment), prepare the manuscript,
Gerby, the PDFs, the site's status and Lean source pages (tools/render.py), the export and its
checks. The edition is exported beside site/book and replaces it only when every check passes,
so a failed build leaves the previous book in place; the site's pages are then rendered again, so
that they link to the new PDFs, whose names carry their build time. runtime/status/book.json records the result
for the status page; runtime/evidence/ holds the reports and runtime/build/ the logs.
"""
import argparse
import fcntl
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
BUILD = RUNTIME / "build"
SITE = ROOT / "site"
STAGE = SITE / ".book-new"
STATUS = RUNTIME / "status/book.json"


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engine", default="xelatex")
    parser.add_argument("--clean", action="store_true", help="remove generated outputs, retaining dependency caches")
    args = parser.parse_args()
    if args.clean:
        for path in [SITE / "book", STAGE, BUILD, RUNTIME / "gerby", RUNTIME / "evidence"]:
            shutil.rmtree(path, ignore_errors=True)
        return
    BUILD.mkdir(parents=True, exist_ok=True)
    lock_file = (RUNTIME / "build.lock").open("w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Waiting for another book build to finish", flush=True)
        fcntl.flock(lock_file, fcntl.LOCK_EX)
    started = time.time()
    state = {"step": "starting"}
    try:
        build(args, state)
    except BaseException as error:
        detail = str(error) if isinstance(error, SystemExit) else repr(error)
        record_status("failed", started, state["step"] + ": " + detail[-600:])
        raise
    finally:
        shutil.rmtree(STAGE, ignore_errors=True)


def record_status(result, started, detail, counts=None):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({"state": result, "updated": now(), "seconds": round(time.time() - started),
                                  "detail": detail, "counts": counts or {}}, indent=2) + "\n")


def build(args, state):
    started = time.time()
    lock = json.loads((ROOT / "toolchain.lock.json").read_text())
    env = dict(os.environ, GERBY_CONFIG_FILE=str(ROOT / "gerby/configuration.py"),
               SOURCE_DATE_EPOCH=str(lock["source_date_epoch"]), FORCE_SOURCE_DATE="1",
               PYTHONNOUSERSITE="1", PYTHONHASHSEED="0", TZ="UTC", BOOK_SITE=str(STAGE))
    python = RUNTIME / ".venv/bin/python"

    def step(title, command, logfile):
        state["step"] = title
        print(title, flush=True)
        with (BUILD / logfile).open("w") as log:
            result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env,
                                    stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            text = (BUILD / logfile).read_text(errors="replace")
            print(text[-12000:], file=sys.stderr)
            raise SystemExit(text.strip().splitlines()[-1][-400:] if text.strip() else "see " + logfile)

    step("Preparing pinned dependencies", [sys.executable, "tools/bootstrap.py"], "bootstrap.log")
    before = (ROOT / "tags.json").read_bytes()
    step("Checking sources and preparing the manuscript", [python, "tools/prepare_manuscript.py"], "prepare.log")
    if before != (ROOT / "tags.json").read_bytes():
        raise SystemExit("Build changed the permanent tag registry")
    step("Rendering Gerby and importing its database", [python, "tools/gerby_build.py"], "gerby-build.log")
    step("Typesetting the book and chapter PDFs", [python, "tools/build_pdf.py", "--engine", args.engine], "pdf.log")
    step("Rendering the status and Lean source pages", [python, "tools/render.py"], "render.log")
    shutil.rmtree(STAGE, ignore_errors=True)
    step("Exporting the complete website", [python, "tools/export_snapshot.py"], "export.log")
    for script in ["check_edition", "check_reading_views", "check_pdf"]:
        step("Validating " + script.removeprefix("check_").replace("_", " "),
             [python, "tools/" + script + ".py"], script + ".log")
    state["step"] = "Replacing site/book"
    old = SITE / ".book-old"
    shutil.rmtree(old, ignore_errors=True)
    if (SITE / "book").exists():
        (SITE / "book").rename(old)
    STAGE.rename(SITE / "book")
    shutil.rmtree(old, ignore_errors=True)
    # Point the status pages, the landing page's status line and site/_redirects at the new PDFs,
    # whose names carry their build time.
    step("Linking the site to the new book", [python, "tools/render.py"], "render-site.log")
    commit = os.environ.get("BOOK_COMMIT")
    if not commit:
        try:
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                             stderr=subprocess.DEVNULL, text=True).strip()
        except subprocess.CalledProcessError:
            commit = None
    tex_env = dict(os.environ)
    if tex_env.get("TEX_LD_LIBRARY_PATH"):
        tex_env["LD_LIBRARY_PATH"] = tex_env["TEX_LD_LIBRARY_PATH"]
    files = sorted(p for p in (SITE / "book").rglob("*") if p.is_file())
    record = {"book_commit": commit, "manuscript_changed_since_commit": not os.environ.get("BOOK_MANUSCRIPT") and bool(subprocess.run(
                  ["git", "status", "--porcelain", "--", "manuscript", "tags.json"], cwd=ROOT,
                  capture_output=True, text=True).stdout.strip()),
              "toolchain": lock, "platform": platform.platform(),
              "python": subprocess.check_output([str(python), "--version"], text=True).strip(),
              "tex": subprocess.check_output([args.engine, "--version"], text=True, env=tex_env).splitlines()[0],
              "tags_sha256": hashlib.sha256(before).hexdigest(),
              "files": {str(p.relative_to(SITE / "book")): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in files}}
    (RUNTIME / "evidence/build-provenance.json").write_text(json.dumps(record, indent=2) + "\n")
    evidence = RUNTIME / "evidence"
    statement_map = json.loads((evidence / "statement-map.json").read_text())
    pdf = json.loads((evidence / "pdf-report.json").read_text())
    presentation = json.loads((evidence / "presentation-report.json").read_text())
    counts = {"tags": sum(1 for line in (BUILD / "tags.csv").read_text().splitlines() if line),
              "statements": statement_map["statements"], "proofs": statement_map["proofs"],
              "lean_links": statement_map["lean_references"], "pages": pdf["pages"],
              "overfull_boxes": pdf["overfull_boxes"], "files": len(files),
              "statements_without_introductions": len(presentation["warnings"])}
    record_status("built", started, "", counts)
    print("Built site/book/ in " + str(round(time.time() - started)) + " s: " + json.dumps(counts), flush=True)


if __name__ == "__main__":
    main()
