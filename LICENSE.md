# Licences

Copyright 2026 Benjamin Antieau and the contributors, except for the parts named under "Not covered".

- **The book** (`book/manuscript/`, `book/plan/`, `book/STYLE.md`, `book/status.json`, `book/tags.json`
  and the Markdown files of this repository) is licensed under the
  [Creative Commons Attribution 4.0 International licence](https://creativecommons.org/licenses/by/4.0/)
  (CC BY 4.0); the full text is in [`LICENSES/CC-BY-4.0.txt`](LICENSES/CC-BY-4.0.txt). Attribute it
  as "The Riemann Hypothesis after Alpöge, by Benjamin Antieau and the contributors", with a link to
  <https://github.com/antieau/rh-after-alpoge>.
- **The code** (everything else under `book/`: `tools/`, `explorer/` apart from its `vendor/`,
  `gerby/`, `Makefile`, the JSON files that configure the build) is licensed under the MIT licence;
  the full text is in [`LICENSES/MIT.txt`](LICENSES/MIT.txt).

## Not covered

- **`lean/`** is Levent Alpöge's Lean development, copied unchanged from the archive he published at
  <https://alpo.ge> (SHA-256 in `book/source.json`). It is here so that the book can link to the
  statements it reads. This repository grants no licence for it; its rights are its author's.
- **Third-party code** keeps its own licence: the patches in `book/gerby/patches/` change
  [gerby-website](https://github.com/gerby-project/gerby-website) and
  [plasTeX](https://github.com/gerby-project/plastex) (both MIT), and `book/explorer/vendor/tce/` is
  [Tau Ceti Explorer](https://github.com/CBirkbeck/tauceti-explorer) (Apache 2.0, with its `LICENSE`
  and `NOTICE`).

Contributions are accepted under the same licences (see [CONTRIBUTING.md](CONTRIBUTING.md)).
