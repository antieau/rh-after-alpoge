# Pinned Tau Ceti Explorer components

Source: https://github.com/CBirkbeck/tauceti-explorer

Commit: `e75bb6012af938d42b078da193d47aee722dbf28`, acquired 2026-11-05.

These upstream files are copied **without modifications**. `UPSTREAM.json` records their SHA-256 hashes. The original Apache-2.0 LICENSE and NOTICE are retained, as are the D3 and KaTeX notices. D3 is loaded; KaTeX is not loaded by this integration. No upstream roadmap data, Tau Ceti Lean library, live polling code, or application controller is included.

KAFKA's separate `field-model.mjs` adapter provides scene objects from `kafka.graph.v1`. `field-renderer.mjs` changes accessibility terminology from roadmap/layer to source division/section, and labels exported SVGs. `field.css` supplies application-specific styling and neutral marks for non-result source material. The shell and inspector are KAFKA code. This is local component reuse, not a published GitHub fork.

For an upstream update, check out the proposed immutable commit, review changes to these files and their input contract, copy the selected files and any required notices, regenerate `UPSTREAM.json`, and run the Node suite plus browser navigation/evidence checks. Never overwrite vendored files from an unpinned branch. Source identities, relation semantics, and proof status remain owned by the canonical registry.

Current adaptation choices:

- Use the `areas` layout; no Mathlib distance or implementation progress is inferred.
- Use galaxies for registry areas, constellations for separate source divisions/editions, stars for section batches, and planets for records.
- Keep all progress fields unknown and all prerequisite-specific edge arrays empty. Read observed citations in the source inspector instead.
- Add orientation rings and subject-neighborhood boundaries in the separate KAFKA renderer; no distance scores or canonical relations are created.
- Retain the original decorative spanning-tree figures as grouping guides, never registry edges.
- Reuse original PR-star and landed-star drawing in an explicitly labeled activity preview; no real KAFKA activity is claimed or recorded. Preview click/keyboard handlers navigate within the atlas, and exported SVGs carry a simulated-activity label.
- Bound each section batch at 48 records: upstream `placePlanets` has six finite rings totalling 69 slots.
- Keep the full original NOTICE even though some referenced components/data are not used here.
