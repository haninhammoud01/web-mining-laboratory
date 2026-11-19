"""
graph_builder.py - Modul untuk membangun graph dan menghitung PageRank.

Berbeda dengan implementasi umum, modul ini:
- Mendukung weighted edges (jumlah tautan antar domain) dan unweighted
- Menghitung PageRank dengan iterasi manual sebagai opsi (selain nx.pagerank)
- Menyediakan metrik tambahan: in-degree, out-degree, density, diameter
- Mengembalikan hasil sebagai DataFrame untuk integrasi UI
- Mendukung export ke GraphML & JSON
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import networkx as nx
import pandas as pd


def build_graph(crawler, weighted: bool = True) -> nx.DiGraph:
    """Bangun directed graph antar domain dari hasil crawler.

    Args:
        crawler: Instance Crawler yang sudah dijalankan.
        weighted: Jika True, weight edge = jumlah tautan antar domain.
            Jika False, semua edge weight = 1.

    Returns:
        DiGraph NetworkX dengan domain sebagai node.
    """
    G = nx.DiGraph()
    # Tambah semua domain yang ditemukan sebagai node
    for domain in crawler.pages_crawled:
        G.add_node(domain)

    # Tambah edge dari hasil crawler
    for (src, dst), count in crawler.edges.items():
        if weighted:
            G.add_edge(src, dst, weight=count)
        else:
            G.add_edge(src, dst, weight=1)

    return G


def pagerank(G: nx.DiGraph, damping: float = 0.85, max_iter: int = 1000) -> dict:
    """Hitung PageRank semua node dengan NetworkX.

    NetworkX secara default menangani dangling node (out-degree=0)
    dengan mendistribusikan PR-nya ke semua node. Inilah yang membuat
    algoritma stabil meskipun ada node yang tidak menaut kemana-mana.

    Args:
        G: DiGraph NetworkX.
        damping: Damping factor (default 0.85).
        max_iter: Maksimum iterasi power iteration.

    Returns:
        Dict {node: PageRank value}. Total = 1.0 (ternormalisasi).
    """
    return nx.pagerank(G, alpha=damping, max_iter=max_iter, tol=1e-9)


def pagerank_manual(G: nx.DiGraph, damping: float = 0.85,
                    max_iter: int = 100, tol: float = 1e-9) -> dict:
    """Implementasi iterasi manual PageRank untuk tujuan edukasi.

    Rumus (Bing Liu, Chapter 7.3):
        PR(i) = (1 - d) / N + d * sum( PR(j) / D_out(j) for j -> i )

    Dangling node (out-degree=0) ditangani dengan mendistribusikan
    PR-nya ke semua node secara merata.

    Args:
        G: DiGraph NetworkX.
        damping: Damping factor (default 0.85).
        max_iter: Maksimum iterasi.
        tol: Toleransi konvergensi (berhenti jika perubahan < tol).

    Returns:
        Dict {node: PageRank value}.
    """
    nodes = list(G.nodes())
    N = len(nodes)
    if N == 0:
        return {}

    # Inisialisasi: semua node dapat 1/N
    pr = {n: 1 / N for n in nodes}

    # Pre-compute out-degree untuk efisiensi
    out_degrees = {n: G.out_degree(n) for n in nodes}

    for _ in range(max_iter):
        new_pr = {}
        # Identifikasi dangling nodes
        dangling_sum = sum(pr[n] for n in nodes if out_degrees[n] == 0)

        for node in nodes:
            # Kontribusi dari in-neighbors
            inflow = 0.0
            for predecessor in G.predecessors(node):
                if out_degrees[predecessor] > 0:
                    inflow += pr[predecessor] / out_degrees[predecessor]

            # Kontribusi dari dangling nodes (didistribusi ke semua)
            dangling_share = damping * dangling_sum / N

            new_pr[node] = (1 - damping) / N + dangling_share + damping * inflow

        # Cek konvergensi
        delta = sum(abs(new_pr[n] - pr[n]) for n in nodes)
        pr = new_pr
        if delta < tol:
            break

    return pr


def compute_metrics(G: nx.DiGraph, pagerank_scores: dict) -> pd.DataFrame:
    """Hitung metrik lengkap untuk setiap node.

    Args:
        G: DiGraph NetworkX.
        pagerank_scores: Dict {node: PageRank}.

    Returns:
        DataFrame dengan kolom: node, page_rank, in_degree, out_degree,
        total_degree, normalized_pagerank.
    """
    rows = []
    if not pagerank_scores:
        return pd.DataFrame()

    max_pr = max(pagerank_scores.values()) or 1.0
    for node in G.nodes():
        pr = pagerank_scores.get(node, 0.0)
        in_d = G.in_degree(node)
        out_d = G.out_degree(node)
        rows.append({
            "node": node,
            "page_rank": pr,
            "in_degree": in_d,
            "out_degree": out_d,
            "total_degree": in_d + out_d,
            "normalized_pagerank": pr / max_pr,
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("page_rank", ascending=False).reset_index(drop=True)
    df.insert(0, "ranking", df.index + 1)
    return df


def graph_summary(G: nx.DiGraph) -> dict:
    """Ringkasan metrik level graph.

    Args:
        G: DiGraph NetworkX.

    Returns:
        Dict dengan: nodes, edges, density, is_strongly_connected, dll.
    """
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    density = nx.density(G)

    summary = {
        "nodes": n_nodes,
        "edges": n_edges,
        "density": round(density, 4),
        "is_directed": G.is_directed(),
        "is_strongly_connected": nx.is_strongly_connected(G)
            if n_nodes > 0 else False,
    }

    # Diameter dan average shortest path (hanya jika strongly connected)
    if n_nodes > 1:
        try:
            if summary["is_strongly_connected"]:
                summary["diameter"] = nx.diameter(G)
                summary["average_shortest_path"] = round(
                    nx.average_shortest_path_length(G), 4
                )
            else:
                # Pakai weakly connected untuk graf yang tidak strongly connected
                summary["diameter"] = None
                summary["average_shortest_path"] = None
                summary["weakly_connected_components"] = nx.number_weakly_connected_components(G)
        except Exception:
            summary["diameter"] = None
            summary["average_shortest_path"] = None

    return summary


def top_n_pagerank(pagerank_scores: dict, n: int = 10) -> pd.DataFrame:
    """Ambil N node dengan PageRank tertinggi.

    Args:
        pagerank_scores: Dict {node: PageRank}.
        n: Jumlah node yang diambil.

    Returns:
        DataFrame dengan ranking, node, page_rank.
    """
    if not pagerank_scores:
        return pd.DataFrame(columns=["ranking", "node", "page_rank"])

    ranked = sorted(pagerank_scores.items(), key=lambda x: -x[1])[:n]
    rows = [{"ranking": i + 1, "node": node, "page_rank": pr}
            for i, (node, pr) in enumerate(ranked)]
    return pd.DataFrame(rows)


def export_graph(G: nx.DiGraph, pagerank_scores: dict, output_dir: str,
                 prefix: str = "crawl") -> dict:
    """Export graph ke beberapa format file.

    Args:
        G: DiGraph NetworkX.
        pagerank_scores: Dict {node: PageRank}.
        output_dir: Folder output (akan dibuat jika belum ada).
        prefix: Prefix nama file.

    Returns:
        Dict {format: filepath} yang berhasil di-export.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Tambah PageRank sebagai node attribute untuk GraphML
    for node in G.nodes():
        G.nodes[node]["pagerank"] = pagerank_scores.get(node, 0.0)
        G.nodes[node]["in_degree"] = G.in_degree(node)
        G.nodes[node]["out_degree"] = G.out_degree(node)

    result = {}

    # Export GraphML (untuk Gephi/Cytoscape)
    graphml_path = output_path / f"{prefix}.graphml"
    nx.write_graphml(G, graphml_path)
    result["graphml"] = str(graphml_path)

    # Export JSON (node-link format)
    json_path = output_path / f"{prefix}.json"
    from networkx.readwrite import json_graph
    import json
    data = json_graph.node_link_data(G)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    result["json"] = str(json_path)

    # Export edges CSV
    edges_path = output_path / f"{prefix}_edges.csv"
    edges_df = pd.DataFrame(
        [{"source": u, "target": v, "weight": d.get("weight", 1)}
         for u, v, d in G.edges(data=True)]
    )
    edges_df.to_csv(edges_path, index=False)
    result["edges_csv"] = str(edges_path)

    # Export pagerank CSV
    pr_path = output_path / f"{prefix}_pagerank.csv"
    pr_df = pd.DataFrame([
        {"node": node, "page_rank": pr}
        for node, pr in sorted(pagerank_scores.items(), key=lambda x: -x[1])
    ])
    pr_df.to_csv(pr_path, index=False)
    result["pagerank_csv"] = str(pr_path)

    return result
