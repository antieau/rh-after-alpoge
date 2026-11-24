# The Riemann Hypothesis after Alpöge

A reading of Levent Alpöge's Lean proof of the Riemann Hypothesis and of the Generalized Riemann
Hypothesis for Dirichlet L-functions; a working draft, not Alpöge's own exposition. Created by
Benjamin Antieau at Resolution. The manuscript builds a tagged Gerby website, a continuous reader, a
complete PDF and chapter PDFs with the pipeline of the Hironaka book (`../../hironaka/book`). It is
published at <https://rh.antieau.workers.dev/>: the status page and plan at the root, the book under
`/book/` and the cited Lean files under `/src/`. Its source is public at
<https://github.com/antieau/rh-after-alpoge>, with Alpöge's Lean beside it.

Drafting is described in [plan/DRAFTING.md](plan/DRAFTING.md) and the style in [STYLE.md](STYLE.md).

## Build

Install Python **3.9**, Git and TeX Live with XeLaTeX (the AMS fonts, Latin Modern, microtype,
xurl, newunicodechar). Then, from this directory:

```sh
make all PYTHON=python3.9
```

`tools/bootstrap.py` prepares everything the build needs under `runtime/`, which Git ignores:

- the renderers in `runtime/deps/`: public upstream plasTeX and gerby-website at pinned commits,
  with the Hironaka book's patches and then this book's overlay;
- Alpöge's archive in `runtime/source/` (`tools/fetch_source.py`, about 250 MB, checked against
  `source.json`; in the public repository, a link to its unpacked copy `../lean` instead) and its declaration index `runtime/decls.sqlite` (`tools/lean.py index`, a few
  minutes). Nothing in the archive is built or run;
- the Python packages of `gerby/requirements-lock.txt` in `runtime/.venv`.

If XeLaTeX cannot find its shared libraries (as on the machine that publishes the site, whose TeX
Live needs the fontconfig in `~/.local/opt/poppler/lib`), set `TEX_LD_LIBRARY_PATH`; it is passed
to TeX alone. A full build takes under two minutes.

| Path | Output |
| --- | --- |
| `site/book/index.html` | Tagged landing page |
| `site/book/read.html`, `site/book/read/` | Complete text, and chapter and section views |
| `site/book/rh-after-alpoge-<time>.pdf`, `site/book/chapter-<TAG>-<time>.pdf` | Complete PDF and chapter PDFs, named with their UTC build time, e.g. `20261121-0145Z` |
| `site/book/resolution.tex`, `site/book/references.bib` | Prepared manuscript and bibliography |
| `site/index.html`, `site/plan.html`, `site/src/` | Status page, plan and Lean source pages (`tools/render.py`) |
| `site/_redirects` | `/book/book.pdf` and `/book/chapter-<TAG>.pdf` to the current PDFs, with a 302 (`tools/render.py`) |
| `site/explorer/` | Tau Ceti Explorer view of the statements, from `explorer/` and `tools/explorer_data.py` (`tools/render.py`; see [explorer/README.md](explorer/README.md)) |
| `runtime/build/` | Prepared TeX, PDF sources and the log of each step |
| `runtime/evidence/` | Statement map, Lean links and the reports of the checks |
| `runtime/status/book.json` | Result of the last build, for the status page |

The build exports the book beside `site/book/` and replaces it only when every check passes, so a
failed build leaves the previous book in place. `make check` reruns the output checks and
`make clean` removes generated output, keeping dependencies.

## Sources

`manuscript/book.json` orders the chapters. Each chapter `<id>` has its own `<id>.tex`,
`transitions-<id>.tex`, `correspondence-<id>.json` and `references-<id>.bib`; the build merges
them. Where two bibliography files define the same key differently, the fuller entry is used and
the conflict is listed in `runtime/evidence/statement-map.json`.

Each `\leanref{<file>}{<declaration>}` links to the file in the public repository, at the tag
that pins the archive: `"browse"` in `source.json` followed by `<file>#L<line>`
(`tools/lean_source.py`). The build fails unless the file is in the pinned archive (whose digest
`toolchain.lock.json` repeats from `source.json`) and the declaration is in `runtime/decls.sqlite`
at a line that names it. A declaration that another declaration or a command generates (a structure
field, a constructor, a `simps` lemma) has no line of its own: it is linked to the declaration of
its parent in the same file, or else to the first line of the file that names it, and marked
"generated". Only a name that the file never mentions fails the build. The PDF and the explorer use
the same links.

## Tags

`tags.json` is the permanent register of tags: four base-36 characters, from `Z000` on. Never
reassign or reuse a tag. Since the labels of a working draft change, `tools/assign_tags.py` (or
`make tags`) gives a fresh tag to each label that has none; a new tag is always one past the
largest ever issued, and the entries of labels that have left the manuscript stay in the register.
The build itself refuses to assign tags: it fails on a label without a tag, and on a tag of the
committed `tags.json` that has disappeared. Run `tools/assign_tags.py` after adding a labelled
chapter, section, subsection or statement, and commit `tags.json` with it.

Sections with many statements are divided into subsections. Statements share the subsection
counter, as in the Stacks project, so Lemma 13.9.4 may follow Subsection 13.9.3. The contents tree
on chapter and section pages goes down to subsections, and a divided section's page lists its
subsections.

## Renderers

`gerby/patches/gerby-website.patch` and `plastex.patch` are byte-for-byte copies of the Hironaka
book's, which reproduce the private `resolution-book` renderer commits recorded in
`toolchain.lock.json`. `gerby/patches/gerby-website-rh.patch` is this book's overlay: its title,
home and about pages, citation page, a contents page for a book without parts, the credit at the
foot of every page and the links to the timestamped PDFs, whose names `gerby/configuration.py` reads
from `runtime/gerby/build/pdf.json`. Bootstrap checks the digest of every patch and the Git tree
after each. To change the overlay, edit `runtime/deps/gerby-website` and run
`python3 tools/lock_renderer.py gerby-website`, which rewrites the patch and its pins. `gerby/configuration.py` is the instance configuration; the templates read
the title and the archive's details from it.

## Publishing

`make all` writes the whole site into `site/`; any static host can serve it. The deployment to
<https://rh.antieau.workers.dev/> (a Cloudflare Worker, which also joins PDFs that are split into
20 MiB parts for its 25 MiB limit) is kept with the private working copy, not here. Only the current
build's PDFs are in `site/`; `site/_redirects` sends the old names, `/book/book.pdf` and
`/book/chapter-<TAG>.pdf`, to them.

## Not yet carried over from the Hironaka book

- The pinned container build (`make container`) and the `dist/` archive.
- Overfull boxes are counted in `runtime/evidence/pdf-report.json` and on the status page, not
  failed; statements without an introduction are reported, not failed.
- Mathematical audits and a review record: there are none yet.
