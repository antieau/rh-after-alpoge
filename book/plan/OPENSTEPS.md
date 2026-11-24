# Resolving one open step

Instructions for an agent given one `\openstep{…}` of the book. Paths are relative to
`lean/rh/book`. Read `plan/DRAFTING.md` and `STYLE.md` first; the standard and the depth floor
there apply.

Many agents work at once, several of them in the same chapter file, each on its own step. So:

- **Find your step.** Your brief gives the chapter `<id>`, the label of the statement it belongs
  to and the text of the `\openstep`. Find it in `manuscript/<id>.tex`, and read the `%` comments
  beside it: they name the Lean declarations involved.
- **Carry it out to the depth floor.** Read the Lean (`python3 tools/lean.py show|deps NAME`,
  `rg`) and write the step as statements and proofs that follow the Lean's argument. Go down to
  stated lemmas that are published results (cited, with a note where the Lean proves them its own
  way), short, or self-contained computations with their `\leanref`. Then delete the `\openstep`.
  If part of the step still can't be done, leave one narrower `\openstep` saying exactly what
  remains.
- **Read, don't infer.** Check every proof you write against the Lean proof line by line. Never
  reconstruct an argument from declaration names or types alone; a step you haven't read stays
  open.
- **State exactly what the Lean states.** A new statement has the Lean declaration's hypotheses
  and all of its conclusions, in its generality: don't specialize it to the case the book uses,
  don't drop clauses nobody uses, and don't add hypotheses. A hypothesis the proof never uses stays,
  marked unused in the statement itself (a note alone is not enough).
- **Cite only what you have checked.** A published result may be cited only with a locator
  (theorem or section number) you have checked against the source. If you can't check it, follow
  the Lean's own proof, or leave an `\openstep`.
- **Size.** When part of a step stays open, give its size in the `%` comment beside it, measured
  with `python3 tools/lean_size.py NAME ...` (lines of Lean below the declarations, following
  imports and stopping at what the book already cites). `tools/lean.py deps` overcounts.
- **Place new material locally.** Put new definitions and lemmas immediately before the statement
  whose proof uses them, in the same section. Give them labels that start with the chapter's
  prefix and contain a word from your step, so they can't collide with another agent's labels.
- **Edit small and local.** Use the Edit tool for every change, with small replacements anchored
  in your own step's text. Read the file again just before each edit. Never rewrite a whole file,
  and never reformat, move or reword text outside your step.
- **Companion files.**
  - Introductions for new statements go in `manuscript/transitions-<id>.tex`, as `% before:`
    blocks inserted just before the block of the statement your step belongs to.
  - Correspondence notes go in `manuscript/correspondence-<id>.json`, as new keys inserted just
    after the key of that statement. Check that the file is still valid JSON after each edit
    (`python3 -m json.tool`).
  - New bibliography entries go at the end of `manuscript/references-<id>.bib`. First check that
    the key isn't already defined in any `manuscript/references*.bib`.
- **Temporary files** go in the session scratchpad under a name containing your step number
  (`open-NN-…`); other agents share that directory.
- **Don't** edit the plan files, `tags.json` or any tool; don't run `tools/assign_tags.py`; don't
  commit; don't start other agents.
- **Live status.** Keep `runtime/status/agents/open-<NN>.json` current (your brief gives `NN`):
  `{"agent": "Open step NN: <label>", "state": "running", "progress": "…", "updated": "<ISO
  UTC>"}`. Set `state` to `done` at the end, with the outcome as `progress`.
- **Checks.** Run `python3 tools/check_style.py --strict manuscript/<id>.tex
  manuscript/transitions-<id>.tex` and `python3 tools/check_refs.py`. Another agent's work in
  progress may show up in `check_refs`; fix only what is yours.
- **Report**, in under 120 words: what you added (labels), whether the open step is gone or what
  remains, and any proof you found that doesn't follow the Lean.
