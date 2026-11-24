// The RH book's explorer page, adapted from KAFKA's atlas/field.mjs. It reads rh.graph.json (written
// by tools/explorer_data.py from the manuscript) and draws it with the pinned Tau Ceti Explorer.
import {buildFieldModel, validateGraph, safeUrl, kindName} from './field-model.mjs';
import {fieldRenderer} from './field-renderer.mjs';

const $ = id => document.getElementById(id), number = n => n.toLocaleString('en');
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }
function button(text, action, cls = 'record-link') { const e = el('button', cls, text); e.addEventListener('click', action); return e; }
function link(text, url, cls = 'secondary') { const e = el('a', cls, text); e.href = url; return e; }
const plural = (n, word, many = word + 's') => `${number(n)} ${n === 1 ? word : many}`;
let data, model, scene, renderer, dataURL, selected = null, focus = null, searchIndex = [];
const requested = new URLSearchParams(location.search);
let chartGuides = requested.get('grid') !== 'off';
if (requested.get('open') === 'only') $('open').value = 'only';

function rebuild() {
  model = buildFieldModel(data, {open: $('open').value});
  // A fixed reference viewport keeps the geography stable as panels open.
  scene = window.TauUniverse.build(model.input, {width: 1204, height: 782});
  // Tau Ceti's faint constellation figures are grouping guides only, never citations.
  renderer.setUniverse(scene, {selectedId: null});
  updateChartGuides();
  selected = null; focus = null; closeDetails();
  const s = model.stats;
  $('scope-count').textContent = `${plural(s.statements, 'statement')} · ${s.chapters} chapters · ${s.sections} sections · ${plural(s.openStatements, 'statement')} with open steps`;
  $('visible-count').textContent = `${plural(s.visible, 'statement')} in view`;
  $('graph-empty').hidden = scene.galaxies.length > 0;
  if (!scene.galaxies.length) { $('graph-empty').firstElementChild.textContent = 'No statements in this view'; $('graph-empty').lastElementChild.textContent = 'Choose all statements.'; }
  catalogue(); breadcrumbs();
}
// Search reaches every statement, also those the open-step filter hides.
function indexSearch() {
  searchIndex = data.nodes.map(n => ({id: n.label, n, text: [n.label, n.tag, n.number, n.title, kindName(n.kind)].join(' ').toLowerCase()}));
  for (const c of data.chapters) searchIndex.push({id: c.id, chapter: c, text: [c.id, c.tag, 'chapter ' + c.number, c.title].join(' ').toLowerCase()});
  for (const s of data.sections) searchIndex.push({id: s.id, section: s, text: [s.id, s.tag, 'section ' + (s.number || ''), s.title].join(' ').toLowerCase()});
}
function updateChartGuides() {
  renderer?.setChartGuides(chartGuides);
  $('chart-guides').setAttribute('aria-pressed', String(chartGuides));
}
function statementButton(n, action, note) {
  const b = button('', action, 'record-link' + ((n.open_steps || []).length ? ' has-open' : ''));
  b.append(el('span', '', `${n.number} ${n.title}`));
  const small = el('small', '', `${kindName(n.kind)}${n.tag ? ' · ' + n.tag : ''} · ${n.label}${note ? ' · ' + note : ''}`);
  if ((n.open_steps || []).length) small.append(el('span', 'open-badge', 'open step'));
  b.append(small);
  return b;
}
function catalogue() {
  const box = $('catalogue'), query = $('search').value.trim().toLowerCase(); box.replaceChildren();
  if (query) {
    const words = query.split(/\s+/), hits = searchIndex.filter(({text}) => words.every(w => text.includes(w)));
    // Exact labels, tags and numbers first.
    hits.sort((a, b) => (b.text.split(' ').includes(query) ? 1 : 0) - (a.text.split(' ').includes(query) ? 1 : 0));
    box.append(el('div', 'catalogue-heading', plural(hits.length, 'match', 'matches')));
    for (const hit of hits.slice(0, 80)) {
      const open = hit.n && (hit.n.open_steps || []).length, b = button('', () => goTo(hit.id), 'search-hit' + (open ? ' has-open' : ''));
      if (hit.n) b.append(el('strong', '', `${hit.n.number} ${hit.n.title}`), el('small', '', `${kindName(hit.n.kind)} · ${hit.n.tag || 'no tag yet'} · ${hit.n.label}${open ? ' · open step' : ''}`));
      else if (hit.chapter) b.append(el('strong', '', `${hit.chapter.number}. ${hit.chapter.title}`), el('small', '', `Chapter · ${hit.chapter.tag || ''}`));
      else b.append(el('strong', '', `${hit.section.number || ''} ${hit.section.title}`), el('small', '', `Section · ${hit.section.tag || ''}`));
      box.append(b);
    }
    if (hits.length > 80) box.append(el('p', 'search-more', 'Showing the first 80 matches. Add a word to narrow them.'));
    if (!hits.length) box.append(el('p', 'empty-state', 'No statement, section or chapter matches.'));
    return;
  }
  box.append(el('div', 'catalogue-heading', 'CHAPTERS'));
  for (const c of data.chapters) {
    const o = model.objects.get(c.id);
    if (!o.labels.length) continue;
    const b = button('', () => navigate(c.id), 'area-button' + (selected === c.id ? ' active' : '') + (o.open ? ' has-open' : ''));
    b.append(el('span', '', `${c.number}. ${c.title}`), el('small', '', number(o.labels.length) + (o.open ? ` · ${o.open} open` : '')));
    box.append(b);
  }
  box.append(el('p', 'search-more', 'Counts are statements; "open" counts those with an open step.'));
}
function breadcrumbs() {
  const box = $('breadcrumbs'); box.replaceChildren(button('The whole book', () => navigate(null), ''));
  let at = focus || selected, chain = [];
  while (at && model.objects.has(at)) { chain.unshift(at); at = model.parents.get(at); }
  if (chain.length > 3) chain = chain.slice(0, 2).concat(chain.slice(-1));
  for (const id of chain) {
    box.append(el('span', '', '/'));
    const o = model.objects.get(id), name = o.type === 'statement' ? `${kindName(o.node.kind)} ${o.node.number}` : o.type === 'chapter' ? `Chapter ${o.chapter.number}` : o.title;
    box.append(button(name, () => navigate(id), id === (focus || selected) ? 'current' : ''));
  }
  $('ascend').disabled = !chain.length;
}
// Navigate to a statement, section or chapter; one that the open-step filter hides brings back all statements.
function goTo(id) {
  if (!model.objects.has(id) && $('open').value !== 'all' && data.nodes.some(n => n.label === id || n.section === id || n.chapter === id)) {
    $('open').value = 'all'; setFilterURL(); rebuild();
  }
  navigate(id);
}
function navigate(id, {animate = true, route = true} = {}) {
  if (id && !model.objects.has(id)) return;
  selected = id; focus = id;
  document.body.classList.remove('catalogue-open'); $('catalogue-button').setAttribute('aria-expanded', 'false');
  if (id) inspect(id); else closeDetails();
  renderer.select(id); catalogue(); breadcrumbs();
  if (route) { const url = new URL(location.href); url.hash = id ? 'node=' + encodeURIComponent(id) : ''; history.pushState(null, '', url); }
  requestAnimationFrame(() => { renderer.resize(); id ? renderer.zoomToView({id}, animate) : renderer.fitAll(animate); });
}
function closeDetails() { $('inspector').hidden = true; document.body.classList.remove('has-selection'); }
function stats(box, items) { const row = el('div', 'detail-stats'); for (const [n, label] of items) { const cell = el('div'); cell.append(el('strong', '', number(n)), el('span', '', label)); row.append(cell); } box.append(row); }
function statementList(box, labels) { for (const label of labels) { const n = model.nodes.get(label); if (n) box.append(statementButton(n, () => goTo(label))); } }
function relationList(box, relations, end, heading, empty) {
  box.append(el('h3', 'section-label', `${heading} (${relations.length})`));
  if (!relations.length) { box.append(el('p', 'detail-note', empty)); return; }
  const sorted = relations.map(r => model.nodes.get(r[end])).filter(Boolean);
  const where = new Map(relations.map(r => [r[end], r.in || []]));
  for (const n of sorted) box.append(statementButton(n, () => goTo(n.label), 'cited in the ' + where.get(n.label).join(' and ')));
}
function inspect(id) {
  const o = model.objects.get(id); if (!o) return;
  $('inspector').hidden = false; document.body.classList.add('has-selection');
  const box = $('inspector-content'); box.replaceChildren(); box.scrollTop = 0;
  const chapterOf = cid => data.chapters.find(c => c.id === cid);
  if (o.type === 'statement') {
    const n = o.node, c = chapterOf(n.chapter), s = data.sections.find(x => x.id === n.section);
    $('detail-kind').textContent = kindName(n.kind).toUpperCase() + ' ' + n.number;
    box.append(el('div', 'detail-caption', `Chapter ${c.number}${s ? ' · ' + (s.number || '') + ' ' + s.title : ''}`), el('h2', 'detail-title', n.title));
    box.append(el('p', 'detail-subtitle', `${kindName(n.kind)} ${n.number} · ${n.tag ? 'Tag ' + n.tag : 'no tag yet: the next book build assigns one'}`));
    const actions = el('div', 'button-row'), tag = (n.links || []).find(l => l.type === 'tag');
    if (tag) {
      actions.append(link('Tagged text ↗', tag.url, 'primary'), link('In the complete text ↗', `../book/read.html#${n.tag}`));
      box.append(actions);
      if (tag.built === false) box.append(el('p', 'detail-note', 'This tag is newer than the last build of the book; its page appears after the next build.'));
    } else box.append(actions);
    const steps = n.open_steps || [];
    if (steps.length) {
      const panel = el('div', 'open-steps'); panel.append(el('h3', '', steps.length === 1 ? 'Open step' : `${steps.length} open steps`));
      for (const step of steps) panel.append(el('p', '', step.text));
      panel.append(el('p', 'detail-note', 'A step the book does not yet carry out, marked in the text where it occurs.'));
      box.append(panel);
    }
    const lean = (n.links || []).filter(l => l.type === 'lean');
    box.append(el('h3', 'section-label', `Lean (${lean.length})`));
    if (!lean.length) box.append(el('p', 'detail-note', 'This statement cites no Lean declaration.'));
    for (const l of lean) {
      const item = l.url && safeUrl(l.url, location.href) ? link('', l.url, 'lean-link') : el('div', 'lean-link');
      item.append(el('code', '', l.decl), el('small', '', `${l.file}${l.line ? ':' + l.line : ''}${l.how && l.how !== 'declaration' ? ' · ' + l.how : ''}`));
      box.append(item);
    }
    relationList(box, model.uses.get(n.label) || [], 'target', 'Uses', 'The statement and its proof cite no other statement.');
    relationList(box, model.usedBy.get(n.label) || [], 'source', 'Used by', 'No statement or proof cites it.');
    box.append(el('p', 'detail-note', "Uses and used by are the book's \\ref citations in a statement and its proof. They are not the dependency graph of the Lean proof, which will come from the cluster build's dependency data."));
    const d = el('details', 'detail-meta'); d.append(el('summary', '', 'Label and source'), el('p', '', `Label: ${n.label}`), el('p', '', `Proof in the book: ${n.has_proof ? 'yes' : 'no'}`)); box.append(d);
    return;
  }
  $('detail-kind').textContent = o.type === 'chapter' ? 'CHAPTER' : o.type === 'section' ? 'SECTION' : 'STATEMENTS';
  const open = o.open || 0;
  if (o.type === 'chapter') {
    const c = o.chapter;
    box.append(el('div', 'detail-caption', `Chapter ${c.number}`), el('h2', 'detail-title', c.title));
    stats(box, [[o.labels.length, 'statements'], [o.sectionIds.length, 'sections'], [open, 'with open steps']]);
    if (c.url) box.append(link('The chapter in the book ↗', c.url, 'primary'));
    box.append(el('h3', 'section-label', 'Sections'));
    for (const sid of o.sectionIds) { const s = model.objects.get(sid), b = button(s.title, () => navigate(sid), 'record-link' + (s.open ? ' has-open' : '')); b.append(el('small', '', plural(s.labels.length, 'statement') + (s.open ? ` · ${s.open} with open steps` : ''))); box.append(b); }
  } else if (o.type === 'section') {
    const c = chapterOf(o.chapterId);
    box.append(el('div', 'detail-caption', `Chapter ${c.number} · section`), el('h2', 'detail-title', o.title));
    stats(box, [[o.labels.length, 'statements'], [o.children.length, o.children.length === 1 ? 'star' : 'stars'], [open, 'with open steps']]);
    if (o.section?.url) box.append(link('The section in the book ↗', o.section.url, 'primary'));
    box.append(el('h3', 'section-label', 'Statements'));
    statementList(box, o.labels);
  } else {
    const s = model.objects.get(o.sectionId);
    box.append(el('div', 'detail-caption', s.title), el('h2', 'detail-title', o.title));
    stats(box, [[o.labels.length, 'statements'], [open, 'with open steps']]);
    if (o.batches > 1) box.append(el('p', 'detail-note', `Star ${o.batch + 1} of ${o.batches} of this section: a star holds at most 48 statements. The numbers are the book's.`));
    statementList(box, o.labels);
  }
  if ($('open').value === 'only') box.append(el('p', 'detail-note', 'Only statements with open steps are shown. Choose all statements to see the rest.'));
}
function restoreRoute() {
  const p = new URLSearchParams(location.hash.slice(1)), tag = p.get('tag'), id = p.get('node') || (tag && model.byTag.get(tag)) || (tag && data.nodes.find(n => n.tag === tag)?.label);
  if (id && (model.objects.has(id) || data.nodes.some(n => n.label === id))) { if (!model.objects.has(id)) goTo(id); else navigate(id, {animate: false, route: false}); }
  else navigate(null, {animate: false, route: false});
}
function setFilterURL() { const u = new URL(location.href); if ($('open').value === 'only') u.searchParams.set('open', 'only'); else u.searchParams.delete('open'); u.hash = ''; history.pushState(null, '', u); }
$('search').addEventListener('input', catalogue);
$('open').addEventListener('change', () => { setFilterURL(); rebuild(); });
$('whole-book').addEventListener('click', () => navigate(null)); $('fit').addEventListener('click', () => navigate(null));
$('ascend').addEventListener('click', () => navigate(model.parents.get(focus || selected) || null));
$('zoom-in').addEventListener('click', () => renderer?.zoomIn()); $('zoom-out').addEventListener('click', () => renderer?.zoomOut());
$('close-inspector').addEventListener('click', () => { closeDetails(); requestAnimationFrame(() => renderer.resize()); });
$('about-button').addEventListener('click', () => $('about').showModal()); $('close-about').addEventListener('click', () => $('about').close());
$('chart-guides').addEventListener('click', () => { chartGuides = !chartGuides; const u = new URL(location.href); if (chartGuides) u.searchParams.delete('grid'); else u.searchParams.set('grid', 'off'); history.replaceState(null, '', u); updateChartGuides(); });
$('catalogue-button').addEventListener('click', () => { const open = document.body.classList.toggle('catalogue-open'); $('catalogue-button').setAttribute('aria-expanded', String(open)); });
$('export-svg').addEventListener('click', () => { if (!renderer) return; const svg = renderer.exportSVG(), url = URL.createObjectURL(new Blob([svg], {type: 'image/svg+xml'})), a = link('', url); a.download = 'rh-explorer.svg'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); });
document.addEventListener('keydown', e => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); document.body.classList.add('catalogue-open'); $('search').focus(); } if (e.key === 'Escape' && !$('about').open) closeDetails(); });
window.addEventListener('popstate', () => { if (!model) return; const p = new URLSearchParams(location.search), o = p.get('open') === 'only' ? 'only' : 'all'; chartGuides = p.get('grid') !== 'off'; updateChartGuides(); if (o !== $('open').value) { $('open').value = o; rebuild(); } restoreRoute(); });

try {
  const asked = requested.get('dataset'), safe = asked ? safeUrl(asked, location.href) : null;
  if (asked && !safe) throw Error('Use an HTTP(S) dataset URL.');
  dataURL = safe || new URL('rh.graph.json', location.href).href;
  const response = await fetch(dataURL, {cache: 'no-cache'});
  if (!response.ok) throw Error(`${dataURL}: HTTP ${response.status}`);
  data = await response.json();
  const errors = validateGraph(data); if (errors.length) throw Error(errors.slice(0, 4).join(' '));
  const when = data.generated ? new Date(data.generated) : null;
  $('edition').textContent = `From the manuscript${data.source?.commit ? ' at ' + data.source.commit.slice(0, 10) : ''}${when && !isNaN(when) ? ', ' + when.toLocaleString('en-GB', {day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC'}) + ' UTC' : ''}`;
  $('source-status').textContent = `${plural(data.counts?.relations ?? data.relations.length, 'citation')} between statements · not Lean dependencies`;
  indexSearch();
  const Renderer = fieldRenderer(window.TauGraph);
  renderer = new Renderer($('graph'), {onSelect: node => navigate(node.id), onClear: () => { selected = null; closeDetails(); catalogue(); },
    onFocus: where => { focus = where.id || null; breadcrumbs(); }, onAspectChange: () => { selected ? renderer.zoomTo(selected, false) : renderer.fitAll(false); }});
  rebuild(); restoreRoute();
} catch (error) { $('edition').textContent = 'LOAD ERROR'; $('scope-count').textContent = 'Could not open the map'; $('graph-empty').hidden = false; $('graph-empty').firstElementChild.textContent = 'Could not load the statements'; $('graph-empty').lastElementChild.textContent = error.message; console.error(error); }
