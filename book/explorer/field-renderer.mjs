// Adapt presentation without editing the pinned upstream renderer. Adapted from KAFKA's
// atlas/field-renderer.mjs: the chart guides are KAFKA's; the open-step marks and the
// terminology are the RH book's. KAFKA's illustrative activity preview is not carried over.
export function fieldRenderer(Base) {
  return class RHFieldRenderer extends Base {
    drawField() {
      super.drawField();
      const {bounds, galaxies} = this.universe;
      if (!galaxies.length) return;
      const pad = Math.max(bounds.w, bounds.h) * .12 + 200;
      const extent = [[bounds.x - pad, bounds.y - pad], [bounds.x + bounds.w + pad, bounds.y + bounds.h + pad]];
      const reach = Math.max(...extent.flatMap(([x]) => extent.map(([, y]) => Math.hypot(x, y))));
      const guides = this.layers.field.append('g').attr('class', 'rh-chart-guides')
        .attr('aria-hidden', 'true').attr('pointer-events', 'none')
        .attr('display', this.chartGuidesVisible === false ? 'none' : null);
      // TCE's thin gold chart lines. These unnumbered rings are orientation artwork: a radius
      // measures nothing.
      guides.selectAll('circle').data(window.d3.range(500, reach, 500)).enter().append('circle')
        .attr('class', 'rh-chart-ring').attr('cx', 0).attr('cy', 0).attr('r', r => r)
        .attr('fill', 'none').attr('stroke', '#dfc186').attr('vector-effect', 'non-scaling-stroke')
        .attr('stroke-width', 1).attr('stroke-opacity', (_, i) => i % 2 ? .1 : .05);
      // The nearest-centre neighbourhoods of the chapters, outlined without moving or connecting anything.
      const diagram = window.d3.voronoi().x(g => g.x).y(g => g.y).extent(extent)(galaxies);
      const boundaries = diagram.edges.filter(e => e?.left && e.right && e[0] && e[1]);
      guides.append('path').attr('class', 'rh-chart-boundaries')
        .attr('d', boundaries.map(e => `M${e[0][0]},${e[0][1]}L${e[1][0]},${e[1][1]}`).join(''))
        .attr('fill', 'none').attr('stroke', '#dfc186').attr('vector-effect', 'non-scaling-stroke')
        .attr('stroke-width', 1).attr('stroke-opacity', .16);
    }
    setChartGuides(visible) {
      this.chartGuidesVisible = !!visible;
      this.layers.field.selectAll('.rh-chart-guides').attr('display', visible ? null : 'none');
      return this;
    }
    renderConstellations(items, k, active) {
      super.renderConstellations(items, k, active);
      this.layers.constellation.selectAll('g.tau-constellation').classed('rh-open', d => d.openStatements > 0)
        .attr('aria-label', d => d.label + '. Section' + (d.openStatements ? `, ${d.openStatements} with open steps` : ''));
    }
    renderStars(items, k, active) {
      super.renderStars(items, k, active);
      this.layers.star.selectAll('g.tau-star').classed('rh-open', d => d.openStatements > 0)
        .attr('aria-label', d => d.label + '. Statements in book order' + (d.openStatements ? `, ${d.openStatements} with open steps` : ''));
    }
    renderPlanets(items, k, active) {
      super.renderPlanets(items, k, active);
      // A dashed ring round a statement that contains an open step: a fact of the manuscript, not a score.
      this.layers.planet.selectAll('g.tau-planet').classed('rh-open', d => d.open > 0)
        .attr('aria-label', d => `${d.label}. ${d.kind}` + (d.open ? ', contains an open step' : ''))
        .each(function (d) {
          const g = window.d3.select(this);
          let ring = g.select('circle.rh-open-ring');
          if (!(d.open > 0)) { ring.remove(); return; }
          if (ring.empty()) ring = g.insert('circle', '.tau-select-ring').attr('class', 'rh-open-ring').attr('fill', 'none')
            .attr('vector-effect', 'non-scaling-stroke').attr('stroke-width', 1.4);
          // A non-scaling stroke dashes in screen pixels, as the star cores of Tau Ceti do.
          ring.attr('r', d.r * 1.6).attr('stroke-dasharray', '3 2');
        });
    }
    exportSVG() {
      return super.exportSVG().replace('aria-label="Tau Ceti mathematics universe"',
        'aria-label="The statements of The Riemann Hypothesis after Alpöge, drawn with Tau Ceti Explorer"');
    }
  };
}
