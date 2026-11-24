# Drafting a chapter

Instructions for whoever drafts a chapter of this book, person or agent. Several chapters are
drafted at once, each in its own files. Paths are relative to `lean/rh/book`.

## Where things are

- **The plan:** your chapter is `plan/chapters/NN-<id>.json`, which lists the statements the chapter
  must cover. Each has its Lean name, file, line, role (`main`, `new` or `standard`) and an informal
  statement from the mapping pass. That statement is a starting point, not a checked one: some were
  read from long lists of hypotheses only in part. For context, read `plan/overview.json`, the other
  chapter files and `runtime/notes/mapping-notes.md`.
- **The Lean:** `runtime/source/lean/src` has 17.4 million lines with no comments. Names are terse,
  and file names often don't match their contents.
  - `python3 tools/lean.py show NAME` prints a declaration's source; `find` and `deps` also exist.
  - Use `rg` for anything else.
  - Nothing is built. Never build or run the Lean.
- **The announcement:** `runtime/remark.txt`.
- **Style:** `STYLE.md` here, and the Hironaka book's `../../hironaka/book/STYLE.md`, whose rules
  it adopts. Model files from the Hironaka book are in `../../hironaka/book/manuscript/`:
  - `core.tex` for statements, proofs and `\leanref` lines;
  - `transitions.tex` for introductory paragraphs;
  - `correspondence.json` for notes.

## Your files

Edit these and nothing else:

- **`manuscript/<id>.tex`**
  - It starts with `\chapter{…}\label{chapter-<id>}` and an opening paragraph of two to four
    sentences.
  - Sections are `\section{…}\label{section-<prefix>-…}`.
  - Statements go in `theorem`, `lemma`, `proposition`, `corollary`, `definition`, `remark`,
    `example` or `situation` environments, with `\label{<prefix>-…}` right after `\begin{…}`.
  - After `\end{…}`, put one `\leanref{<path relative to src>}{<full Lean name>}` line for each
    declaration the statement corresponds to.
  - Proofs go in `proof`.
  - Use plain LaTeX with amsmath and amssymb, and no custom macros: write `\operatorname{Gal}` and
    so on.
- **`manuscript/transitions-<id>.tex`:** one introductory paragraph per statement, as
  `% before: <label>` blocks. Each has two to four sentences on why the statement is needed at that
  point.
- **`manuscript/correspondence-<id>.json`:** `{label: note}` for each statement whose relation to
  the Lean needs saying.
- **`manuscript/references-<id>.bib`:** BibTeX for what you cite, with keys like `Hir64` and `Kol07`
  (author initials and year).
- **`plan/chapters/NN-<id>.json`:** keep it current, as described under "Progress".

## Order of work

1. Set the plan's `state` to `drafting`. Before drafting, choose a label for each planned statement
   and write it into a `label` field on that statement in the plan file. Other chapters
   cross-reference your statements by these labels, and you theirs. Cite another chapter as
   `Chapter~\ref{chapter-<id>}`, and one of its statements by the `label` in its plan file.
2. Read each planned declaration with `tools/lean.py show`, together with the definitions its
   statement uses. Keep unfolding until the statement can be written in mathematical terms.
3. Draft the chapter, then its introductory paragraphs and its correspondence notes.
4. Run `python3 tools/check_style.py --strict manuscript/<id>.tex manuscript/transitions-<id>.tex`
   until it prints nothing. Then run `python3 tools/render.py` and check that the chapter appears in
   `site/read.html`.

## The standard

- **Faithful statements.** Each statement says what the Lean declaration it cites says, with all of
  its hypotheses. Read the type; don't trust the names or the plan's paraphrase.
  - A bundle of hypotheses or a `Prop`-valued definition is stated as mathematics.
  - Some Lean statements are odd: a vacuous field, `True` in a conjunction, or a name that claims
    more than is proved. For these, state what is proved and say so in the note.
- **Readable on its own** (`STYLE.md`, "Statements"). "Let …" sentences introduce every object, and
  a recurring class of data gets a Definition.
- **New results get proofs.**
  - Follow the structure of the Lean proof, written in mathematical language, one step per sentence
    where that is clearer.
  - Leave out the Lean bookkeeping: casts, coercions, instances and renaming.
  - A number theorist should be able to check the argument from the proof and the statements it
    cites.
  - Where the Lean proof is a long routine computation, state its result and what it rests on.
- **Standard results** are stated in full, in the form the Lean proves, and cited to the published
  source, with no proof. The correspondence note says how the Lean statement relates to the
  published theorem: the same, a special case, weaker, or related only in name.
- **What to add:** definitions and lemmas beyond the plan where the chapter needs them to be readable
  or a proof needs them. Add each to the plan file with its role. Don't restate other chapters.
- **When you can't tell:** if you can't determine what a declaration means or how a step works,
  write a TeX comment line `% OPEN: …` at that point and list it in your report. Don't guess.

## Progress

The status page at <https://rh.antieau.workers.dev> shows the plan files to people at Resolution and
refreshes every two minutes. At each milestone, update these fields:

- `state`: `drafting`, then `drafted` when you finish;
- `progress`: one sentence on where you are, for example "Sections 1–2 drafted; writing the proof
  of the window bound.";
- `updated`: an ISO time in UTC.

## Rules

- Edit only your files. Don't edit `tools/`, `STYLE.md`, `manuscript/book.json`, `status.json` or
  other chapters' files. If you need a change there, put it in your report.
- Don't commit or push. Don't build or run the Lean. Don't start other agents.
- List any style warnings you think should stay as deliberate exceptions in your report. They go
  into `tools/style-exceptions.txt` at review.

## Report

Keep it under 300 words:

- the number of statements and proofs;
- the labels of the chapter's main results;
- where the Lean differs from the plan, the announcement or the literature;
- the `OPEN` items;
- any changes you need to shared files.

# The completion pass

The drafts are complete chapter by chapter. The completion pass makes each chapter one a number
theorist can check. It works on one chapter at a time, in that chapter's files, by the standard
above, and does three things.

1. **Names.** Apply the names in `STYLE.md` rule 13 throughout the chapter, its introductions and
   its notes. Labels keep their names.
2. **OPEN items.** Resolve each `% OPEN:` line: read the Lean until the step is understood, then
   write it as statements and proofs and delete the line. If a step still can't be resolved, keep
   the line and say exactly what is missing.
3. **Proofs.** Replace each proof that only summarizes ("summarized from the statements it uses",
   "a long computation") with a proof that follows the Lean's argument step by step. Add lemmas
   where the argument needs them. A standard result stays a citation.

   A proof that still only summarizes, or says what it rests on without following the Lean, carries
   a `% OPEN:` line saying so. The status page counts these lines, so they show what is left.

## Live status

The status page lists every agent at work. Keep `runtime/status/agents/<your-file>.json` current
(the brief names the file):

```json
{"agent": "Chapter 7: completion pass", "state": "running",
 "progress": "One sentence on what you are doing now.", "updated": "<ISO time, UTC>"}
```

Write it when you start and at least every 20 minutes. When you finish, set `state` to `done` and
write the outcome as `progress`. Also keep the chapter's plan file current, as above.

## Checks before you finish

- `python3 tools/check_style.py --strict` on your files;
- `python3 tools/check_refs.py`, which must print nothing;
- `runtime/.venv/bin/python tools/assign_tags.py --dry-run`, then
  `runtime/.venv/bin/python tools/prepare_manuscript.py`, which checks every `\leanref` against the
  archive.

Don't run `tools/build.py`: the publisher rebuilds and deploys the book when the chapters change.

# The depth floor

Decided on 20 November: the book follows the Lean down to a floor, not to the bottom.

- **When a step is done.** Its proof follows the Lean's argument down to lemmas that the book
  states, each of which is one of these:
  - a published result, cited, with a note comparing the Lean's form;
  - short: a few lines of argument with no new idea;
  - a self-contained computation, given with its result and its `\leanref`.

  Such lemmas need no proof in the book, and no open mark.
- **Follow the Lean.** A proof follows the Lean's argument. If another argument is shorter, it may
  appear as a remark after the proof, but the proof itself is the Lean's.
- **References.** Where the Lean proves a published result in its own way, citing the published
  result is enough, with a note saying how the Lean's statement compares.
- **Open steps, visibly.** A step the book still doesn't carry out is marked in the text, inside the
  proof it belongs to, as `\openstep{One sentence, for the reader, saying what is not yet written
  out.}` The build prints it as an "Open step." paragraph, and the status page lists every one.
  Details for the next writer, such as Lean names, go in ordinary `%` comments next to it. An old
  `% OPEN:` comment either becomes an `\openstep` or goes away because the floor is reached.
