# The Riemann Hypothesis after Alpöge

On 20 November 2026 Levent Alpöge announced a proof of the Riemann Hypothesis and of the Generalized
Riemann Hypothesis for Dirichlet $L$-functions ([announcement](https://alpo.ge/remark.pdf)). The
proof is a Lean development of 17.4 million lines, published as an archive and nothing else. This
repository holds a human-readable book of that proof and the Lean it reads.

The book is a reading of Alpöge's Lean, not his own exposition, and it is a working draft. Each
statement says what the Lean states, and each proof follows the Lean's argument down to lemmas that
are cited, short or computations; steps not yet written out are marked as open.

**Read it at <https://rh.antieau.workers.dev/>**: the web book with a page for every statement, the
complete PDF and one per chapter, and an explorer of the statements and the citations between them.

## What is here

- `book/`: the book. `book/manuscript/` holds the chapters as TeX, `book/plan/` how the proof goes
  and the chapter plan, `book/STYLE.md` the style rules, and `book/tools/` the build of the website
  and the PDFs. See [book/README.md](book/README.md).
- `lean/`: Alpöge's Lean development, 175,000 files, exactly as unpacked from his archive (pinned by
  SHA-256 in `book/source.json`). Nothing in it is changed. The tag `lean-9631b4f0` marks the commit
  that added it, and the book's Lean links point there.

To clone the book without `lean/` (about 1.4 GB unpacked):

```sh
git clone --filter=blob:none --sparse https://github.com/antieau/rh-after-alpoge
cd rh-after-alpoge && git sparse-checkout set book
```

## Working on the book

From `book/`:

```sh
python3 tools/fetch_source.py   # link runtime/source to ../lean, or without it download and check the archive
python3 tools/lean.py index     # index its declarations into runtime/decls.sqlite
python3 tools/lean.py show UpperTheory.FinalTheorems.everyCharacter   # also: find, deps
python3 tools/check_style.py    # the style rules
python3 tools/check_refs.py     # references, labels and environments
make all PYTHON=python3.9       # the website and the PDFs, into site/ (see book/README.md)
```

Nothing here builds or runs Alpöge's Lean; the tools read its text.

## Contributing

Corrections are welcome, from a typo to a statement that does not say what the Lean says. Open an
issue, or a pull request; [CONTRIBUTING.md](CONTRIBUTING.md) says how.

## Licences

The book's text is under CC BY 4.0 and its code under the MIT licence. `lean/` is Alpöge's and is
not covered. See [LICENSE.md](LICENSE.md).

---

Created by Benjamin Antieau at Resolution.
