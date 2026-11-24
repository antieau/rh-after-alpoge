// Run from the book directory: node --test explorer/
// Adapted from KAFKA's atlas/field-model.test.mjs to the RH book's data.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {buildFieldModel, validateGraph, safeUrl, ORBIT_CAPACITY, SCHEMA} from './field-model.mjs';

const here = new URL('.', import.meta.url), book = new URL('../', here);
const context = {window: {}};
vm.runInNewContext(fs.readFileSync(new URL('vendor/tce/src/universe.js', here), 'utf8'), context);
const universe = input => context.window.TauUniverse.build(input, {width: 1204, height: 782});

const chapter = (id, number) => ({id, number: String(number), title: 'Chapter ' + id, file: id + '.tex', tag: null});
const section = (id, chapterId, number) => ({id, number, title: 'Section ' + id, chapter: chapterId, tag: null});
const statement = (label, {chapter = 'chapter-a', section = 'section-a1', kind = 'lemma', number = '1.1.1', open = 0} = {}) =>
  ({label, tag: null, kind, number, title: 'Title of ' + label, chapter, section, has_proof: true, links: [],
    open_steps: Array.from({length: open}, (_, i) => ({text: 'Open ' + i, tex: 'Open ' + i}))});
const graph = (nodes, relations = []) => ({schema: SCHEMA, chapters: [chapter('chapter-a', 1), chapter('chapter-b', 2)],
  sections: [section('section-a1', 'chapter-a', '1.1'), section('section-b1', 'chapter-b', '2.1')], nodes, relations});

test('every statement of a long section gets a finite position in the upstream layout', () => {
  const nodes = Array.from({length: 240}, (_, i) => statement('s' + i, {number: '1.1.' + (i + 1)}));
  const m = buildFieldModel(graph(nodes)), u = universe(m.input);
  assert.equal(m.input.stars.size, 5); assert.equal(u.planets.length, 240);
  for (const planets of m.input.planets.values()) assert.ok(planets.length <= ORBIT_CAPACITY);
  assert.ok(u.planets.every(n => Number.isFinite(n.x) && Number.isFinite(n.y) && n.orbit));
  assert.equal(m.objects.get('view:batch/section-a1/1').title, 'Statements 1.1.49–1.1.96');
});
test('statements before the first section of a chapter keep their chapter', () => {
  const m = buildFieldModel(graph([statement('front', {section: null, number: '1.0.1'}), statement('x')]));
  assert.equal(m.parents.get(m.parents.get('front')), 'view:front/chapter-a');
  assert.equal(m.parents.get('view:front/chapter-a'), 'chapter-a');
  assert.ok(universe(m.input).byId.has('front'));
});
test('the open-step filter keeps exactly the statements with open steps, under their own labels', () => {
  const g = graph([statement('a', {open: 2}), statement('b'), statement('c', {chapter: 'chapter-b', section: 'section-b1', open: 1})]);
  const all = buildFieldModel(g), only = buildFieldModel(g, {open: 'only'});
  assert.equal(all.stats.visible, 3); assert.equal(only.stats.visible, 2);
  assert.deepEqual([...only.input.planets.values()].flat().map(p => p.id).sort(), ['a', 'c']);
  assert.ok([...only.input.planets.values()].flat().every(p => p.open > 0));
  assert.equal(all.objects.get('chapter-a').open, 1); assert.equal(all.input.stars.get('view:batch/section-a1/0').openStatements, 1);
  assert.equal(all.stats.openSteps, 3);
});
test('citations never become prerequisite edges, and nothing carries a progress score', () => {
  const r = {source: 'a', target: 'b', type: 'cites', in: ['proof']};
  const m = buildFieldModel(graph([statement('a'), statement('b')], [r]));
  assert.equal(m.uses.get('a')[0], r); assert.equal(m.usedBy.get('b')[0], r);
  for (const key of ['starEdges', 'planetEdges', 'constellationEdges', 'relatedEdges']) assert.deepEqual(m.input[key], []);
  assert.ok(m.input.groups.every(g => g.progress === null));
  assert.ok(m.input.constellations.every(c => c.progress === null));
  assert.ok([...m.input.stars.values()].every(s => s.progress === null));
  const u = universe(m.input);
  assert.ok([...u.byId.values()].every(n => n.progress == null)); assert.equal(u.core, null);
});
test('the adapter does not change the data, and the layout is deterministic', () => {
  const g = graph([statement('a'), statement('b'), statement('c', {chapter: 'chapter-b', section: 'section-b1'})]), before = JSON.stringify(g);
  const a = universe(buildFieldModel(g).input), b = universe(buildFieldModel(g).input);
  assert.equal(JSON.stringify(g), before);
  assert.deepEqual(a.planets.map(n => [n.id, n.x, n.y]), b.planets.map(n => [n.id, n.x, n.y]));
});
test('validation names unknown chapters, sections and relation ends; URLs are http(s) only', () => {
  assert.deepEqual(validateGraph(graph([statement('a')])), []);
  assert.equal(validateGraph(graph([statement('a', {chapter: 'nowhere'})])).length, 1);
  assert.equal(validateGraph(graph([statement('a', {section: 'nowhere'})])).length, 1);
  assert.equal(validateGraph(graph([statement('a')], [{source: 'a', target: 'gone'}])).length, 1);
  assert.equal(validateGraph(graph([statement('a'), statement('a')])).length, 1);
  assert.equal(safeUrl('javascript:alert(1)', 'https://rh.example/explorer/'), null);
  assert.equal(safeUrl('../src/A.lean.html#L3', 'https://rh.example/explorer/'), 'https://rh.example/src/A.lean.html#L3');
});
test('all vendored files match the pinned upstream manifest', () => {
  const manifest = JSON.parse(fs.readFileSync(new URL('vendor/tce/UPSTREAM.json', here)));
  assert.match(manifest.commit, /^[a-f0-9]{40}$/);
  assert.ok(manifest.files.length >= 9);
  for (const file of manifest.files) {
    const bytes = fs.readFileSync(new URL('vendor/tce/' + file.path, here));
    assert.equal(createHash('sha256').update(bytes).digest('hex'), file.sha256, file.path);
  }
});
test('the page is buildless and requests nothing from another host', () => {
  for (const name of fs.readdirSync(here).filter(f => /\.(html|mjs|css)$/.test(f) && !f.endsWith('.test.mjs'))) {
    const text = fs.readFileSync(new URL(name, here), 'utf8');
    assert.doesNotMatch(text, /<script[^>]+src=["']?(https?:)?\/\//i, name);
    assert.doesNotMatch(text, /<link[^>]+href=["']?(https?:)?\/\//i, name);
    assert.doesNotMatch(text, /(import|from)\s*\(?\s*["'](https?:)?\/\//, name);
    assert.doesNotMatch(text, /url\(\s*["']?(https?:)?\/\//, name);
    assert.doesNotMatch(text, /fetch\(\s*["'`](https?:)?\/\//, name);
  }
});

// The book's own data, written afresh from the manuscript by tools/explorer_data.py.
const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'rh-explorer-test-')), out = path.join(scratch, 'rh.graph.json');
process.on('exit', () => fs.rmSync(scratch, {recursive: true, force: true}));
let rh = null, browse = null, failure = null;
try {
  execFileSync('python3', [new URL('tools/explorer_data.py', book).pathname, '--out', out], {stdio: 'pipe'});
  rh = JSON.parse(fs.readFileSync(out, 'utf8'));
  browse = JSON.parse(fs.readFileSync(new URL('source.json', book), 'utf8')).browse;
} catch (error) { failure = error; }

test('the RH data is written and valid', () => {
  assert.equal(failure, null, failure && String(failure.stderr || failure));
  assert.deepEqual(validateGraph(rh), []);
  assert.ok(rh.nodes.length > 0 && rh.chapters.length > 0);
  assert.equal(rh.counts.statements, rh.nodes.length); assert.equal(rh.counts.relations, rh.relations.length);
});
test('every RH statement gets a finite position in the actual TCE layout, with or without the filter', () => {
  for (const open of ['all', 'only']) {
    const m = buildFieldModel(rh, {open}), u = universe(m.input);
    const expected = open === 'all' ? rh.nodes.length : rh.nodes.filter(n => n.open_steps.length).length;
    assert.equal(u.planets.length, expected);
    for (const planets of m.input.planets.values()) assert.ok(planets.length <= ORBIT_CAPACITY);
    for (const n of rh.nodes) if (open === 'all' || n.open_steps.length) {
      const p = u.byId.get(n.label);
      assert.ok(p && p.level === 'planet' && Number.isFinite(p.x) && Number.isFinite(p.y), n.label);
    }
    assert.ok([...u.byId.values()].every(n => Number.isFinite(n.x) && Number.isFinite(n.y)));
  }
});
test('RH statements carry their label, tag, kind, title, place and links in the published form', () => {
  const chapters = new Set(rh.chapters.map(c => c.id));
  for (const n of rh.nodes) {
    assert.ok(n.label && n.kind && n.title && n.number, n.label);
    assert.match(n.number, /^\d+\.\d+\.\d+$/, n.label);
    assert.ok(chapters.has(n.chapter), n.label);
    assert.ok(Array.isArray(n.open_steps) && n.open_steps.every(s => typeof s.text === 'string'), n.label);
    const tags = n.links.filter(l => l.type === 'tag');
    if (n.tag) assert.deepEqual(tags.map(l => l.url), [`../book/tag/${n.tag}.html`], n.label);
    for (const l of n.links.filter(l => l.type === 'lean')) {
      assert.ok(l.file && l.decl, n.label);
      if (l.line) assert.equal(l.url, `${browse}${l.file}#L${l.line}`, n.label);
    }
  }
  const lean = rh.nodes.flatMap(n => n.links.filter(l => l.type === 'lean'));
  if (fs.existsSync(new URL('runtime/decls.sqlite', book))) assert.ok(lean.filter(l => l.line).length >= lean.length * .99, 'Lean lines found');
});
test('RH relations are citations between statements that the manuscript makes', () => {
  const labels = new Set(rh.nodes.map(n => n.label)), seen = new Set();
  for (const r of rh.relations) {
    assert.ok(labels.has(r.source) && labels.has(r.target) && r.source !== r.target);
    assert.equal(r.type, 'cites'); assert.ok(r.in.length && r.in.every(w => w === 'statement' || w === 'proof'));
    assert.ok(!seen.has(r.source + '>' + r.target)); seen.add(r.source + '>' + r.target);
  }
  assert.match(rh.semantics.relations, /not the dependency graph of the Lean proof/);
});
test('RH statement count agrees with an independent count of the manuscript', () => {
  const manifest = JSON.parse(fs.readFileSync(new URL('manuscript/book.json', book)));
  let environments = 0;
  for (const entry of manifest.entries) {
    const file = new URL('manuscript/' + entry.file, book);
    if (!fs.existsSync(file)) continue;
    const text = fs.readFileSync(file, 'utf8').replace(/(?<!\\)%.*$/gm, '');
    environments += (text.match(/\\begin\{(theorem|proposition|lemma|corollary|definition|situation|remark|example|conjecture|notation)\}/g) || []).length;
  }
  // A statement without a label, or one whose environment does not close, is skipped and counted.
  const s = rh.skipped, counted = rh.nodes.length + s['statements without a label'] + s['duplicate labels'].length;
  assert.ok(counted <= environments && environments <= counted + s['unclosed environments or groups'], `${counted} counted, ${environments} in the manuscript`);
});
