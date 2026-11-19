"""Build D3.js-based Flourish-style network graph module.

This module provides a function to render an interactive network graph
using D3.js force-directed layout with Flourish Studio styling:
- Multi-color palette (warm colors for high PageRank, cool for low)
- Curved edges (bezier interpolation)
- Smart labels (auto-show for top nodes, hover for others)
- Dark background with subtle gradient
- Glow effect on important nodes
- Smooth zoom & pan
"""

from __future__ import annotations

import json
import math
from typing import Dict

import networkx as nx
import pandas as pd


def _normalize_pr(pr_values: Dict[str, float]) -> Dict[str, float]:
    """Normalize PageRank values to 0-1 range."""
    if not pr_values:
        return {}
    pr_max = max(pr_values.values())
    pr_min = min(pr_values.values())
    if pr_max == pr_min:
        return {n: 0.5 for n in pr_values}
    return {n: (v - pr_min) / (pr_max - pr_min) for n, v in pr_values.items()}


def _flourish_color(t: float, is_seed: bool = False) -> str:
    """Generate Flourish-style color based on PageRank (0-1).

    Palette: warm (orange/pink) for high PageRank, cool (purple/blue) for low.

    Args:
        t: Normalized PageRank value (0-1).
        is_seed: If True, return gold (seed color).

    Returns:
        Hex color string.
    """
    if is_seed:
        return "#fbbf24"  # Gold/amber for seed

    # Multi-stop palette (diverging warm -> cool)
    # Stops: indigo -> purple -> pink -> orange (Flourish-like)
    stops = [
        (0.0, (99, 102, 241)),    # Indigo-500
        (0.33, (168, 85, 247)),   # Purple-500
        (0.66, (236, 72, 153)),   # Pink-500
        (1.0, (251, 146, 60)),    # Orange-400
    ]

    for i in range(len(stops) - 1):
        t0, (r0, g0, b0) = stops[i]
        t1, (r1, g1, b1) = stops[i + 1]
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0)
            r = int(r0 + (r1 - r0) * f)
            g = int(g0 + (g1 - g0) * f)
            b = int(b0 + (b1 - b0) * f)
            return f"rgb({r}, {g}, {b})"

    # Fallback
    return "rgb(99, 102, 241)"


def render_flourish_graph(
    G: nx.DiGraph,
    pr: Dict[str, float],
    seed: str,
    metrics_df: pd.DataFrame,
    top_n: int = 30,
    height: int = 720,
    dark_mode: bool = True,
) -> str:
    """Render Flourish-style network graph as self-contained HTML.

    Args:
        G: Directed graph.
        pr: PageRank dict.
        seed: Seed domain (will be highlighted gold).
        metrics_df: DataFrame with metrics.
        top_n: Number of top PageRank nodes to display.
        height: Canvas height in pixels.
        dark_mode: If True, use dark theme.

    Returns:
        Self-contained HTML string with D3.js network graph.
    """
    if G.number_of_nodes() == 0:
        return "<div style='padding:40px;text-align:center;color:#9aa4b2;'>Tidak ada node untuk ditampilkan.</div>"

    # Subgraph dengan top nodes
    keep_nodes = set(metrics_df.head(top_n)["node"].tolist()) if len(metrics_df) > 0 else set(G.nodes())
    keep_nodes.add(seed)
    H = G.subgraph(keep_nodes).copy()

    if H.number_of_nodes() == 0:
        return "<div style='padding:40px;text-align:center;color:#9aa4b2;'>Graph kosong.</div>"

    # Normalize PageRank
    pr_norm = _normalize_pr({n: pr.get(n, 0) for n in H.nodes()})

    # Build nodes JSON
    nodes_json = []
    for node in H.nodes():
        t = pr_norm.get(node, 0)
        is_seed = node == seed
        # Logarithmic size scaling (15-40)
        size = 15 + 25 * math.sqrt(t) if t > 0 else 15
        if is_seed:
            size = 38

        color = _flourish_color(t, is_seed=is_seed)
        in_deg = H.in_degree(node)
        out_deg = H.out_degree(node)
        nodes_json.append({
            "id": node,
            "label": node,
            "size": size,
            "color": color,
            "pageRank": pr.get(node, 0),
            "inDegree": in_deg,
            "outDegree": out_deg,
            "isSeed": is_seed,
            "normalizedPr": t,
        })

    # Build edges JSON (top 200 to keep performance)
    edges_json = []
    max_weight = max((d.get("weight", 1) for _, _, d in H.edges(data=True)), default=1)
    edges = list(H.edges(data=True))
    # Sort by weight desc, limit to top 200
    edges.sort(key=lambda x: -x[2].get("weight", 1))
    edges = edges[:200]

    for u, v, d in edges:
        w = d.get("weight", 1)
        # Width 1.5-6 based on weight (lebih tebal agar curve terlihat)
        width = 1.5 + 4.5 * math.sqrt(w / max_weight) if max_weight > 0 else 1.5
        edges_json.append({
            "source": u,
            "target": v,
            "weight": w,
            "width": width,
        })

    # Theme
    if dark_mode:
        bg_color = "#0a0e17"
        text_color = "#e2e8f0"
        text_muted = "#94a3b8"
        edge_color_base = "rgba(180, 199, 220, 0.55)"  # Lebih terang & tebal
        edge_color_highlight = "rgba(251, 191, 36, 0.95)"
    else:
        bg_color = "#fafbfc"
        text_color = "#0f172a"
        text_muted = "#64748b"
        edge_color_base = "rgba(100, 116, 139, 0.6)"
        edge_color_highlight = "rgba(251, 146, 60, 0.95)"

    # Determine which labels to show (top 5 PageRank + seed)
    top_label_nodes = set(metrics_df.head(5)["node"].tolist()) if len(metrics_df) > 0 else set()
    top_label_nodes.add(seed)

    # Build complete HTML
    html = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Network Graph - Flourish Style</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body, html {{
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
    background: {bg_color};
    color: {text_color};
    overflow: hidden;
    height: 100vh;
    width: 100vw;
  }}
  #graph-container {{
    width: 100%;
    height: {height}px;
    position: relative;
    background: {bg_color};
  }}
  /* Radial gradient overlay for depth */
  #graph-container::before {{
    content: '';
    position: absolute;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    width: 600px;
    height: 600px;
    border-radius: 50%;
    background: radial-gradient(circle, {'rgba(99, 102, 241, 0.08)' if dark_mode else 'rgba(99, 102, 241, 0.05)'} 0%, transparent 70%);
    pointer-events: none;
    z-index: 0;
  }}
  svg {{
    width: 100%;
    height: 100%;
    position: relative;
    z-index: 1;
  }}
  .node {{
    cursor: pointer;
    transition: opacity 0.2s;
  }}
  .node:hover {{
    opacity: 0.85;
  }}
  .node-label {{
    font-size: 11px;
    font-weight: 500;
    pointer-events: none;
    text-anchor: middle;
    fill: {text_color};
    text-shadow: 0 1px 3px {bg_color};
    user-select: none;
  }}
  .node-label.seed {{
    font-size: 14px;
    font-weight: 700;
    fill: #fbbf24;
  }}
  .link {{
    fill: none;
    stroke: {edge_color_base};
    pointer-events: none;
    transition: stroke 0.2s;
  }}
  .link.highlighted {{
    stroke: {edge_color_highlight};
    stroke-width: 2px !important;
  }}
  /* Tooltip */
  .tooltip {{
    position: absolute;
    background: {bg_color};
    color: {text_color};
    border: 1px solid {text_muted};
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 12px;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s;
    max-width: 240px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    z-index: 100;
  }}
  .tooltip h4 {{
    margin: 0 0 6px 0;
    font-size: 14px;
    font-weight: 700;
  }}
  .tooltip .meta {{
    color: {text_muted};
    font-size: 11px;
    margin-top: 4px;
  }}
  .tooltip .pr-value {{
    font-weight: 600;
    color: #fbbf24;
  }}
  /* Legend */
  .legend {{
    position: absolute;
    top: 16px;
    right: 16px;
    background: {bg_color};
    border: 1px solid {text_muted};
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 11px;
    color: {text_muted};
    z-index: 10;
  }}
  .legend .item {{
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
  }}
  .legend .item:last-child {{
    margin-bottom: 0;
  }}
  .legend .dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
  }}
  /* Controls hint */
  .controls-hint {{
    position: absolute;
    bottom: 12px;
    left: 16px;
    font-size: 10px;
    color: {text_muted};
    z-index: 10;
    opacity: 0.7;
  }}
</style>
</head>
<body>
<div id="graph-container">
  <div class="legend">
    <div class="item">
      <span class="dot" style="background:#fbbf24;"></span>
      <span>Seed (URL awal)</span>
    </div>
    <div class="item">
      <span class="dot" style="background:#fb923c;"></span>
      <span>PageRank tinggi</span>
    </div>
    <div class="item">
      <span class="dot" style="background:#ec4899;"></span>
      <span>PageRank menengah</span>
    </div>
    <div class="item">
      <span class="dot" style="background:#a855f7;"></span>
      <span>PageRank rendah</span>
    </div>
  </div>
  <div class="controls-hint">Scroll untuk zoom - Drag untuk geser - Hover untuk detail</div>
  <div class="tooltip" id="tooltip"></div>
</div>

<script>
const nodes = {json.dumps(nodes_json)};
const links = {json.dumps(edges_json)};
const topLabelNodes = {json.dumps(list(top_label_nodes))};
const seedNode = "{seed}";

const width = document.getElementById('graph-container').clientWidth;
const height = {height};

const svg = d3.select('#graph-container').append('svg')
  .attr('viewBox', `0 0 ${{width}} ${{height}}`)
  .attr('width', '100%')
  .attr('height', '100%');

// SVG definitions for glow filter
const defs = svg.append('defs');
const glow = defs.append('filter')
  .attr('id', 'glow')
  .attr('x', '-50%').attr('y', '-50%')
  .attr('width', '200%').attr('height', '200%');
glow.append('feGaussianBlur')
  .attr('stdDeviation', '4')
  .attr('result', 'coloredBlur');
const feMerge = glow.append('feMerge');
feMerge.append('feMergeNode').attr('in', 'coloredBlur');
feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

// Container for zoom
const g = svg.append('g');

// Zoom behavior
const zoom = d3.zoom()
  .scaleExtent([0.2, 5])
  .on('zoom', (event) => {{
    g.attr('transform', event.transform);
  }});
svg.call(zoom);

// Force simulation
const simulation = d3.forceSimulation(nodes)
  .force('link', d3.forceLink(links).id(d => d.id).distance(d => 80 + 20 * (1 - Math.min(d.weight / 10, 1))).strength(0.4))
  .force('charge', d3.forceManyBody().strength(-180).distanceMax(400))
  .force('center', d3.forceCenter(width / 2, height / 2))
  .force('collision', d3.forceCollide().radius(d => d.size + 8))
  .force('x', d3.forceX(width / 2).strength(0.04))
  .force('y', d3.forceY(height / 2).strength(0.04))
  .alpha(1)
  .alphaDecay(0.025)
  .velocityDecay(0.4);

// Draw links (curved with quadratic bezier)
const link = g.append('g')
  .attr('stroke-opacity', 0.7)
  .selectAll('path')
  .data(links)
  .enter().append('path')
  .attr('class', 'link')
  .attr('stroke-width', d => d.width)
  .attr('fill', 'none');

// Draw nodes
const node = g.append('g')
  .selectAll('circle')
  .data(nodes)
  .enter().append('g')
  .attr('class', 'node')
  .call(d3.drag()
    .on('start', dragStarted)
    .on('drag', dragged)
    .on('end', dragEnded));

// Glow circle (for seed)
node.filter(d => d.isSeed)
  .append('circle')
  .attr('r', d => d.size + 4)
  .attr('fill', 'none')
  .attr('stroke', d => d.color)
  .attr('stroke-width', 2)
  .attr('opacity', 0.3)
  .attr('filter', 'url(#glow)');

// Main node circle
node.append('circle')
  .attr('r', d => d.size)
  .attr('fill', d => d.color)
  .attr('stroke', d => d.isSeed ? '#92400e' : 'rgba(255,255,255,0.2)')
  .attr('stroke-width', d => d.isSeed ? 3 : 1);

// Labels - show for top PageRank + seed by default
const showLabelFor = (d) => topLabelNodes.includes(d.id) || d.isSeed;

const label = g.append('g')
  .selectAll('text')
  .data(nodes)
  .enter().append('text')
  .attr('class', d => 'node-label' + (d.isSeed ? ' seed' : ''))
  .attr('dy', d => d.size + 14)
  .attr('opacity', d => showLabelFor(d) ? 1 : 0)
  .text(d => d.id);

// Tooltip
const tooltip = d3.select('#tooltip');

node.on('mouseover', function(event, d) {{
    // Show label for hovered node
    label.filter(l => l.id === d.id).attr('opacity', 1);
    // Highlight connected edges
    link.filter(l => l.source.id === d.id || l.target.id === d.id)
      .classed('highlighted', true);
    // Dim others
    node.style('opacity', 0.3);
    d3.select(this).style('opacity', 1);

    tooltip.transition().duration(100).style('opacity', 1);
    tooltip.html(`
      <h4>${{d.id}}</h4>
      <div>PageRank: <span class="pr-value">${{d.pageRank.toFixed(5)}}</span></div>
      <div>In-degree: ${{d.inDegree}} - Out-degree: ${{d.outDegree}}</div>
      ${{d.isSeed ? '<div class="meta">Seed domain</div>' : ''}}
    `)
      .style('left', (event.pageX + 14) + 'px')
      .style('top', (event.pageY - 14) + 'px');
  }})
  .on('mouseout', function(event, d) {{
    // Restore label visibility
    label.filter(l => l.id === d.id).attr('opacity', l => showLabelFor(l) ? 1 : 0);
    // Unhighlight edges
    link.classed('highlighted', false);
    // Restore opacity
    node.style('opacity', 1);

    tooltip.transition().duration(200).style('opacity', 0);
  }});

// Tick function: update positions
simulation.on('tick', () => {{
  // Curved edges menggunakan quadratic bezier dengan offset perpendicular
  link.attr('d', function(d) {{
    const sx = d.source.x, sy = d.source.y;
    const tx = d.target.x, ty = d.target.y;
    const dx = tx - sx, dy = ty - sy;
    const dist = Math.sqrt(dx * dx + dy * dy);
    // Midpoint
    const mx = (sx + tx) / 2;
    const my = (sy + ty) / 2;
    // Offset perpendicular ke midpoint (untuk kelengkungan dramatis)
    // offset = 25% dari jarak
    const offset = dist * 0.25;
    const nx = -dy / (dist || 1) * offset;
    const ny = dx / (dist || 1) * offset;
    // Quadratic bezier: M sx,sy Q mx+nx,my+ny tx,ty
    return `M${{sx}},${{sy}} Q${{mx + nx}},${{my + ny}} ${{tx}},${{ty}}`;
  }});

  node.attr('transform', d => `translate(${{d.x}},${{d.y}})`);
  label.attr('x', d => d.x).attr('y', d => d.y);
}});

// Drag functions
function dragStarted(event, d) {{
  if (!event.active) simulation.alphaTarget(0.3).restart();
  d.fx = d.x;
  d.fy = d.y;
}}
function dragged(event, d) {{
  d.fx = event.x;
  d.fy = event.y;
}}
function dragEnded(event, d) {{
  if (!event.active) simulation.alphaTarget(0);
  d.fx = null;
  d.fy = null;
}}

// Run simulation
for (let i = 0; i < 300; i++) simulation.tick();
</script>
</body>
</html>"""

    return html
