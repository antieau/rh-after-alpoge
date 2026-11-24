# Explorer

A [Tau Ceti Explorer](https://github.com/CBirkbeck/tauceti-explorer) view of the book's statements, at
`/explorer/` on the site. Chapters are galaxies, sections constellations, the statements of a section
stars of at most 48 (upstream's bound) in book order, and statements planets. Selecting a statement shows
its kind, number, title and open steps, links to its tag page and to the Lean it cites, and the
statements it cites and that cite it. Those relations are the book's `\ref` citations, not the Lean's
dependency graph. The page is buildless and makes no requests to another host.

`tools/render.py` copies this directory to `site/explorer/` on every pass, without the tests and this
file, and writes the data, `site/explorer/rh.graph.json`, with `tools/explorer_data.py`. A statement can
be opened at `explorer/index.html#node=<label>` or `#tag=<TAG>`. Run the tests from the book directory:

```sh
node --test explorer/*.test.mjs
```

They check the adapter on small graphs, the vendored files against `vendor/tce/UPSTREAM.json`, that the
page loads nothing from another host, and, on data written afresh from the manuscript, that every
statement gets a finite position in the actual TCE layout and that its links have the published form.

## Where the files came from

KAFKA's atlas: `projects/kafka/atlas/` of a local checkout of this monorepo, branch
`codex/kafka-remote-workspace` (not on origin), commit `9a0e2281231b0c0f0410ee7ab8fa3d10c7c3d31e`.
Upstream: <https://github.com/CBirkbeck/tauceti-explorer> at `e75bb6012af938d42b078da193d47aee722dbf28`.

| Here | From | Changes |
| --- | --- | --- |
| `vendor/tce/` | KAFKA `atlas/vendor/tce/`, itself upstream's files at `e75bb60` | None: byte-identical, with LICENSE, NOTICE, D3 and `UPSTREAM.json` |
| `index.html` | KAFKA `atlas/field.html` | The book's header, filter, legend and about text; no activity preview |
| `field.mjs` | KAFKA `atlas/field.mjs` | Reads `rh.graph.json`; the statement inspector, open-step filter, search and `#tag=` routes |
| `field-model.mjs` | KAFKA `atlas/field-model.mjs` | Chapters, sections, batches and statements; validation and `safeUrl` from KAFKA's `graph.mjs` |
| `field-renderer.mjs` | KAFKA `atlas/field-renderer.mjs` | Chart guides kept; activity preview dropped; open-step marks added |
| `field.css` | KAFKA `atlas/field.css` | The book's marks and legend |
| `field-model.test.mjs` | KAFKA `atlas/field-model.test.mjs` | Tests on the book's data |
| `../tools/explorer_data.py` | New | Writes `rh.graph.json` from the manuscript |

To merge the two copies into one shared module once both have landed: `vendor/tce/` is the same in both
and moves as it is; the chart guides of `field-renderer.mjs` and the shell of `index.html` and
`field.mjs` are common; each project keeps its own data adapter (`field-model.mjs`), inspector and tests.
