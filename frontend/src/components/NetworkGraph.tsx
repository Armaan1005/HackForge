import cytoscape, { type Core, type ElementDefinition } from 'cytoscape';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { GEdge, GNode } from '../lib/types';

// Identity by SHAPE + label first, colour second (3 categorical slots max), so it survives colour-blindness.
const SHAPE: Record<string, string> = {
  provider: 'round-rectangle', member: 'ellipse', member_group: 'ellipse', facility: 'rectangle', owner: 'diamond',
  bank: 'hexagon', address: 'tag', location: 'triangle', claim: 'round-tag', claim_group: 'round-tag',
};
const GROUP: Record<string, 1 | 2 | 3 | 0> = { provider: 1, owner: 2, bank: 2, facility: 3, location: 3, address: 3 };

const C = {
  s1: '#2b8a63', s2: '#b5651d', s3: '#8f8f86', neutral: '#d3d3cc', text: '#1d1d1f', edge: '#d3d3cc',
  bad: '#b0473f', surface: '#ffffff', hi: '#a86a1c',
};

export function NetworkGraph({ nodes, edges, visibleIds, highlightEvidence, onSelect, injectedIds }: {
  nodes: GNode[]; edges: GEdge[]; visibleIds?: Set<string>; highlightEvidence?: string | null;
  onSelect?: (n: GNode | null) => void; injectedIds?: Set<string>;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const [ready, setReady] = useState(false);
  const c = C;

  const elements = useMemo<ElementDefinition[]>(() => [
    ...nodes.map(n => ({ data: { id: n.id, label: n.label, type: n.type, risk: n.risk ?? 0, flagged: n.flagged ? 1 : 0, inCase: n.in_case ? 1 : 0, group: GROUP[n.type] ?? 0, injected: injectedIds?.has(n.id) ? 1 : 0, raw: n } })),
    ...edges.map(e => ({ data: { id: e.id, source: e.source, target: e.target, type: e.type, weight: e.weight, ev: e.evidence_ids.join(' ') } })),
  ], [nodes, edges, injectedIds]);

  useEffect(() => {
    if (!ref.current) return;
    const inst = cytoscape({
      container: ref.current, elements, wheelSensitivity: 0.25, minZoom: 0.3, maxZoom: 2.5,
      layout: { name: 'cose', animate: false, padding: 40, nodeRepulsion: () => 9000, idealEdgeLength: () => 90, randomize: false } as cytoscape.LayoutOptions,
      style: [
        { selector: 'node', style: {
          shape: ((el: cytoscape.NodeSingular) => SHAPE[el.data('type')] ?? 'ellipse') as unknown as cytoscape.Css.NodeShape,
          'background-color': (el: cytoscape.NodeSingular) => ({ 1: c.s1, 2: c.s2, 3: c.s3, 0: c.neutral } as Record<number, string>)[el.data('group')],
          width: (el: cytoscape.NodeSingular) => (el.data('type') === 'provider' ? 34 + el.data('risk') / 6 : el.data('type').endsWith('group') ? 30 : 24),
          height: (el: cytoscape.NodeSingular) => (el.data('type') === 'provider' ? 34 + el.data('risk') / 6 : el.data('type').endsWith('group') ? 30 : 24),
          label: 'data(label)', 'font-size': 10, color: c.text, 'text-valign': 'bottom', 'text-margin-y': 5,
          'text-wrap': 'ellipsis', 'text-max-width': '110px', 'border-width': 2, 'border-color': c.surface,
          'transition-property': 'opacity, border-color, border-width', 'transition-duration': 250,
        } },
        { selector: 'node[flagged = 1]', style: { 'border-color': c.bad, 'border-width': 3 } },
        { selector: 'node[inCase = 0]', style: { opacity: 0.65 } },
        { selector: 'node[injected = 1]', style: { 'border-color': c.hi, 'border-width': 4, 'border-style': 'dashed' } },
        { selector: 'edge', style: {
          width: (el: cytoscape.EdgeSingular) => Math.min(1.5 + Math.log2(1 + (el.data('weight') || 1)) * 0.7, 5), 'line-color': c.edge, 'curve-style': 'bezier',
          'target-arrow-shape': (el: cytoscape.EdgeSingular) => (el.data('type') === 'referral' ? 'triangle' : 'none'), 'target-arrow-color': c.edge, 'arrow-scale': 0.8,
          label: (el: cytoscape.EdgeSingular) => (el.data('type') === 'referral' ? `${el.data('weight')} referrals` : ''), 'font-size': 8, color: c.text, 'text-rotation': 'autorotate', 'text-background-color': c.surface, 'text-background-opacity': 0.85, 'text-background-padding': '2px',
        } },
        { selector: 'edge[type = "referral"]', style: { 'line-style': 'solid' } },
        { selector: 'edge[type = "owned_by"], edge[type = "uses_bank"]', style: { 'line-style': 'dashed' } },
        { selector: '.hidden', style: { display: 'none' } },
        { selector: '.hl', style: { 'line-color': c.hi, 'target-arrow-color': c.hi, width: 4, 'z-index': 10 } },
        { selector: 'node.hl', style: { 'border-color': c.hi, 'border-width': 4 } },
        { selector: ':selected', style: { 'overlay-color': c.s1, 'overlay-opacity': 0.15, 'overlay-padding': 6 } },
      ],
    });
    inst.on('tap', 'node', e => onSelect?.(e.target.data('raw')));
    inst.on('tap', e => { if (e.target === inst) onSelect?.(null); });
    cy.current = inst;
    setReady(true);
    return () => { inst.destroy(); cy.current = null; };
  }, [elements]); // eslint-disable-line react-hooks/exhaustive-deps

  // Time Machine: hide anything not present yet
  useEffect(() => {
    const inst = cy.current; if (!inst) return;
    inst.batch(() => inst.elements().forEach(el => { el.toggleClass('hidden', !!visibleIds && !visibleIds.has(el.id())); }));
  }, [visibleIds, ready]);

  // Evidence highlight: edges citing the evidence + their endpoints
  useEffect(() => {
    const inst = cy.current; if (!inst) return;
    inst.batch(() => {
      inst.elements().removeClass('hl');
      if (highlightEvidence) inst.edges().filter(e => (e.data('ev') as string).split(' ').includes(highlightEvidence)).forEach(e => { e.addClass('hl'); e.connectedNodes().addClass('hl'); });
    });
  }, [highlightEvidence, ready]);

  return (
    <div className="graph-box">
      <div ref={ref} style={{ position: 'absolute', inset: 0 }} aria-label="Relationship graph" role="img" />
      <div className="graph-legend" aria-label="Graph legend">
        <span><span className="legend-swatch" style={{ background: c.s1, borderRadius: 3 }} />Provider</span>
        <span><span className="legend-swatch" style={{ background: c.s2, transform: 'rotate(45deg) scale(.8)' }} />Owner / bank</span>
        <span><span className="legend-swatch" style={{ background: c.s3 }} />Facility / location</span>
        <span><span className="legend-swatch" style={{ background: c.neutral, borderRadius: '50%' }} />Members / claims</span>
        <span><span className="legend-swatch" style={{ border: `2px solid ${c.bad}`, borderRadius: 3 }} />Flagged</span>
        <span>→ referral · - - ownership</span>
      </div>
    </div>
  );
}
