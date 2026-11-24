# The plan of the book

The status page reads these files; keep them current as work proceeds.

- `overview.json`: `{"overview": "...", "updated": "<ISO time>"}`. The overview says how the proof
  goes, in plain mathematical English with `$...$` for mathematics, paragraphs separated by blank
  lines. It follows `STYLE.md` and never uses Lean names.
- `chapters/NN-<id>.json`, one per chapter, `NN` giving the order:

  ```json
  {
    "id": "main-theorems",
    "title": "…",
    "state": "mapping | planned | drafting | drafted | reviewed",
    "summary": "Two to four sentences: what the chapter proves and why the proof needs it.",
    "timeline": [20],
    "progress": "One sentence on what is happening to this chapter now.",
    "updated": "<ISO time>",
    "statements": [
      {
        "lean": "Full.Lean.name",
        "file": "path/relative/to/src.lean",
        "line": 13,
        "role": "main | new | standard",
        "reference": "For a standard result, the published source if known.",
        "statement": "The statement in words, with $...$ for mathematics."
      }
    ]
  }
  ```

  `timeline` lists the numbered steps of the timeline in Alpöge's announcement that the chapter
  covers. A chapter's TeX goes in `manuscript/<id>.tex` once drafting starts.
