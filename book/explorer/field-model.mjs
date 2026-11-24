// The RH book's read-only adapter to the pinned Tau Ceti Explorer scene contract, adapted from
// KAFKA's atlas/field-model.mjs. Chapters are galaxies, sections constellations, batches of at most
// ORBIT_CAPACITY statements stars, and statements planets. Statement labels are the planets' ids;
// every other id the view makes starts with "view:" and is never a label of the book.

export const SCHEMA = 'rh.explorer.graph.v1';
export const ORBIT_CAPACITY = 48; // Upstream places at most 69 planets per star.
export const KIND_NAMES = {theorem:'Theorem', proposition:'Proposition', lemma:'Lemma', corollary:'Corollary',
  definition:'Definition', situation:'Situation', remark:'Remark', example:'Example', conjecture:'Conjecture', notation:'Notation'};
export const kindName = kind => KIND_NAMES[kind] || String(kind || 'Statement').replace(/^./, c => c.toUpperCase());
const push = (map, key, value) => { if (!map.has(key)) map.set(key, []); map.get(key).push(value); };
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

// Structural checks of the data file; the manuscript itself is checked by the book's build.
export function validateGraph(graph) {
  if (!graph || typeof graph !== 'object') return ['The data is not a JSON object.'];
  const errors = [];
  if (graph.schema !== SCHEMA) errors.push(`Expected schema ${SCHEMA}, found ${graph.schema}.`);
  for (const key of ['chapters', 'sections', 'nodes', 'relations']) if (!Array.isArray(graph[key])) errors.push(`The data has no ${key} list.`);
  if (errors.length) return errors;
  const chapters = new Set(graph.chapters.map(c => c.id)), sections = new Set(graph.sections.map(s => s.id)), labels = new Set();
  for (const n of graph.nodes) {
    if (!n.label) { errors.push('A statement has no label.'); continue; }
    if (labels.has(n.label)) errors.push(`The label ${n.label} is used twice.`);
    labels.add(n.label);
    if (!chapters.has(n.chapter)) errors.push(`${n.label} names an unknown chapter.`);
    if (n.section != null && !sections.has(n.section)) errors.push(`${n.label} names an unknown section.`);
  }
  for (const r of graph.relations) if (!labels.has(r.source) || !labels.has(r.target)) errors.push(`A relation ${r.source} → ${r.target} names an unknown statement.`);
  return errors;
}

// Only http(s) URLs, resolved against base; anything else (javascript:, data:) is refused.
export function safeUrl(url, base) {
  if (typeof url !== 'string' || !url) return null;
  try { const u = new URL(url, base); return ['http:', 'https:'].includes(u.protocol) ? u.href : null; } catch { return null; }
}

export function buildFieldModel(graph, {open = 'all'} = {}) {
  const nodes = new Map(graph.nodes.map(n => [n.label, n]));
  const hasOpen = n => (n.open_steps || []).length > 0;
  const visible = graph.nodes.filter(n => open !== 'only' || hasOpen(n));
  const sectionById = new Map(graph.sections.map(s => [s.id, s]));
  const objects = new Map(), parents = new Map();
  const groups = graph.chapters.map((c, i) => {
    const title = `${c.number}. ${c.title}`;
    objects.set(c.id, {id:c.id, type:'chapter', title, chapter:c, labels:[], open:0, sectionIds:[]});
    // Book order runs clockwise round the map; the direction is a seed, not a measurement.
    return {id:c.id, label:title, short:`Chapter ${c.number}`, direction:-160 + i * 360 / Math.max(1, graph.chapters.length), progress:null, progressLabel:''};
  });
  const sections = new Map();
  for (const n of visible) {
    const chapter = objects.get(n.chapter);
    if (!chapter) continue;
    const id = n.section ?? `view:front/${n.chapter}`;
    if (!sections.has(id)) {
      const s = sectionById.get(id);
      const entry = {id, type:'section', title:s ? `${s.number ? s.number + ' ' : ''}${s.title}` : 'Before the first section',
        section:s || null, chapterId:n.chapter, labels:[], open:0, children:[]};
      sections.set(id, entry); objects.set(id, entry); parents.set(id, n.chapter); chapter.sectionIds.push(id);
    }
    const entry = sections.get(id);
    entry.labels.push(n.label); chapter.labels.push(n.label);
    if (hasOpen(n)) { entry.open++; chapter.open++; }
  }
  const stars = new Map(), planets = new Map();
  for (const section of sections.values()) {
    const batches = Math.ceil(section.labels.length / ORBIT_CAPACITY);
    for (let b = 0; b < batches; b++) {
      const labels = section.labels.slice(b * ORBIT_CAPACITY, (b + 1) * ORBIT_CAPACITY);
      const first = nodes.get(labels[0]), last = nodes.get(labels[labels.length - 1]);
      const title = labels.length === 1 ? `${kindName(first.kind)} ${first.number}` : `Statements ${first.number}–${last.number}`;
      const id = `view:batch/${section.id}/${b}`, openCount = labels.filter(l => hasOpen(nodes.get(l))).length;
      objects.set(id, {id, type:'batch', title, sectionId:section.id, chapterId:section.chapterId, labels, batch:b, batches, open:openCount});
      parents.set(id, section.id); section.children.push(id);
      stars.set(id, {label:title, top:true, progress:null, progressLabel:'', openStatements:openCount});
      planets.set(id, labels.map(label => {
        const n = nodes.get(label), steps = (n.open_steps || []).length;
        objects.set(label, {id:label, type:'statement', title:n.title, node:n});
        parents.set(label, id);
        return {id:label, label:`${n.number} ${n.title}`, kind:n.kind,
          summary:(n.tag ? 'Tag ' + n.tag : n.label) + (steps ? ' · ' + plural(steps, 'open step') : ''),
          moons:[], refinement:false, open:steps};
      }));
    }
  }
  const constellations = [...sections.values()].map(s => ({id:s.id, galaxyId:s.chapterId, label:s.title, starIds:s.children,
    progress:null, progressLabel:'', distance:null, openStatements:s.open}));
  // Citations are the book's \ref's, not the Lean's dependencies. They stay in the inspector,
  // out of TCE's prerequisite-specific edge arrays.
  const uses = new Map(), usedBy = new Map();
  for (const r of graph.relations) { push(uses, r.source, r); push(usedBy, r.target, r); }
  const byTag = new Map(graph.nodes.filter(n => n.tag).map(n => [n.tag, n.label]));
  for (const c of graph.chapters) if (c.tag) byTag.set(c.tag, c.id);
  for (const s of graph.sections) if (s.tag && sections.has(s.id)) byTag.set(s.tag, s.id);
  return {input:{layout:'areas', groups, fields:[], constellations, stars, planets, starEdges:[], planetEdges:[], constellationEdges:[], relatedEdges:[]},
    objects, nodes, parents, uses, usedBy, byTag,
    stats:{statements:graph.nodes.length, visible:visible.length, chapters:groups.filter(g => objects.get(g.id).labels.length).length,
      sections:sections.size, batches:stars.size, openStatements:graph.nodes.filter(hasOpen).length,
      openSteps:graph.nodes.reduce((t, n) => t + (n.open_steps || []).length, 0), relations:graph.relations.length,
      leanLinks:graph.nodes.reduce((t, n) => t + (n.links || []).filter(l => l.type === 'lean').length, 0)}};
}
