# Contributing

Corrections and improvements are welcome. The most useful are statements that do not say what the
Lean says, proofs that skip or misdescribe a step of the Lean's argument, and passages that are hard
to follow. Typos are welcome too.

## Issues

Open an issue for anything you find. Name the statement by its tag, the four characters in its
page's address (`https://rh.antieau.workers.dev/book/tag/Z0A1.html` is tag `Z0A1`), and, where it
matters, the Lean declaration that its "Lean" link points to.

## Pull requests

The text is in `book/manuscript/`. Each chapter `<id>` has four files:

- `<id>.tex`: the statements, their proofs and the `\leanref{<file>}{<declaration>}` lines that tie
  each statement to the Lean;
- `transitions-<id>.tex`: the short paragraph printed above each statement, keyed by its label;
- `correspondence-<id>.json`: notes on how a statement relates to the Lean;
- `references-<id>.bib`: the chapter's bibliography.

The rules that every change keeps:

1. **Faithfulness.** A statement says exactly what the Lean states, with its hypotheses. A proof
   follows the Lean's argument; a shorter argument may appear only as a remark. A step not yet
   written out is marked with `\openstep{...}`.
2. **Labels are permanent.** Every label has a permanent tag (`book/tags.json`) that pages and
   citations use. Do not rename or delete a label. A new statement gets a new label; leave
   `book/tags.json` alone and the tag is assigned when the change is taken in.
3. **Style.** [book/STYLE.md](book/STYLE.md) gives the style rules. The mathematics does not mention
   the formalization; that belongs in `\leanref` lines and correspondence notes.
4. **Leave `lean/` alone.** It is Alpöge's archive, unchanged, and it changes only when the book
   moves to a new version of it.

Before you open a pull request, run from `book/`:

```sh
python3 tools/check_style.py
python3 tools/check_refs.py
```

A full build (`make all PYTHON=python3.9`, see [book/README.md](book/README.md)) is welcome but not
required.

## How a pull request is taken in

The book is written in a private repository, and this one is its published copy. A pull request
accepted here is applied there with you as its author, and comes back here with the next update of
the copy. The pull request is then closed with a link to the commit that carries it, rather than
merged with GitHub's button.

## Licence of contributions

By opening a pull request you agree that your contribution is licensed as the rest of the
repository is: text under CC BY 4.0 and code under the MIT licence (see [LICENSE.md](LICENSE.md)).
