"""
app.py - Web Crawler + PageRank Analyzer (Streamlit)

Tampilan minimalis aesthetic dengan dark/light mode toggle.
Layout dibedakan dari implementasi umum: sidebar pengaturan + 3-tab layout.

Jalankan:
    streamlit run app.py --server.port 8501
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

# Path setup supaya bisa di-import dari folder yang sama
sys.path.insert(0, str(Path(__file__).parent))
from crawler import Crawler, normalize_url, get_domain
from graph_builder import build_graph, pagerank, compute_metrics, graph_summary, export_graph, top_n_pagerank
from database import init_db, save_crawl_result, list_crawls, get_crawl_detail, delete_crawl

# ---------------------------------------------------------------------------
# Konfigurasi halaman
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Web Crawler PageRank Analyzer",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Path setup
BASE_DIR = Path(__file__).parent
EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)
DB_PATH = BASE_DIR / "crawl_history.db"
init_db(str(DB_PATH))

# ---------------------------------------------------------------------------
# Tema & styling
# ---------------------------------------------------------------------------
def apply_theme(dark: bool) -> None:
    """Apply dark/light theme via custom CSS.

    Streamlit tidak punya native theme toggle, jadi kita inject CSS
    untuk override warna default.
    """
    if dark:
        bg = "#0b0f17"
        surface = "#141a26"
        text = "#e6edf3"
        text_muted = "#9aa4b2"
        border = "#1f2937"
        accent = "#3b82f6"
    else:
        bg = "#ffffff"
        surface = "#fafafa"
        text = "#0f172a"
        text_muted = "#475569"
        border = "#e2e8f0"
        accent = "#0f172a"

    st.markdown(f"""
    <style>
    /* Override Streamlit default theme */
    .stApp {{
        background-color: {bg};
        color: {text};
    }}
    .stSidebar {{
        background-color: {surface};
        border-right: 1px solid {border};
    }}
    /* Section header */
    .section-title {{
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1px;
        text-transform: uppercase;
        color: {text_muted};
        margin-bottom: 12px;
        padding-bottom: 4px;
        border-bottom: 1px solid {border};
    }}
    /* Hero */
    .hero {{
        padding: 32px 0 24px;
        border-bottom: 1px solid {border};
        margin-bottom: 24px;
    }}
    .hero-title {{
        font-size: 28px;
        font-weight: 600;
        letter-spacing: -0.4px;
        color: {text};
        margin: 0 0 8px;
    }}
    .hero-subtitle {{
        font-size: 15px;
        color: {text_muted};
        max-width: 720px;
    }}
    /* Stat card */
    .stat-card {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 16px 20px;
    }}
    .stat-label {{
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        color: {text_muted};
        margin-bottom: 6px;
    }}
    .stat-value {{
        font-size: 22px;
        font-weight: 600;
        color: {text};
        word-break: break-all;
        line-height: 1.2;
    }}
    .stat-value.small {{
        font-size: 15px;
    }}
    /* Table tweaks */
    .stDataFrame [data-baseweb="table"] {{
        background-color: {surface};
    }}
    /* Form input */
    .stTextInput > div > div > input {{
        background-color: {surface};
        color: {text};
        border: 1px solid {border};
    }}
    /* Tab style */
    .stTabs [data-baseweb="tab-list"] {{
        background-color: transparent;
        border-bottom: 1px solid {border};
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {text_muted};
        font-weight: 500;
    }}
    .stTabs [aria-selected="true"] {{
        color: {text} !important;
        border-bottom: 2px solid {accent};
    }}
    /* Footer */
    .footer {{
        margin-top: 48px;
        padding-top: 24px;
        border-top: 1px solid {border};
        font-size: 12px;
        color: {text_muted};
        text-align: center;
    }}
    /* Pill / chip */
    .pill {{
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        background: {surface};
        border: 1px solid {border};
        font-size: 12px;
        color: {text_muted};
        margin: 2px 4px 2px 0;
    }}
    /* Remove Streamlit default padding */
    .block-container {{
        padding-top: 24px;
        max-width: 1200px;
    }}
    </style>
    """, unsafe_allow_html=True)


# Initialize theme state
if "theme_dark" not in st.session_state:
    st.session_state["theme_dark"] = True

apply_theme(st.session_state["theme_dark"])

# ---------------------------------------------------------------------------
# Header (hero) - tanpa toggle di main area (dipindah ke sidebar)
# ---------------------------------------------------------------------------
st.markdown("""
<div class="hero">
  <div class="hero-title">Web Crawler & PageRank Analyzer</div>
  <div class="hero-subtitle">
    Masukkan URL, pilih kedalaman crawl, lalu sistem akan menelusuri tautan,
    membangun directed graph antar halaman, dan menghitung PageRank.
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar pengaturan
# ---------------------------------------------------------------------------
with st.sidebar:
    # Toggle theme di paling atas sidebar
    theme_col1, theme_col2 = st.columns([3, 2])
    with theme_col1:
        st.markdown('<div class="section-title">Tema</div>', unsafe_allow_html=True)
    with theme_col2:
        if st.session_state["theme_dark"]:
            if st.button("Light", use_container_width=True, key="toggle_to_light"):
                st.session_state["theme_dark"] = False
                st.rerun()
        else:
            if st.button("Dark", use_container_width=True, key="toggle_to_dark"):
                st.session_state["theme_dark"] = True
                st.rerun()

    st.markdown('<div class="section-title">Pengaturan Crawl</div>', unsafe_allow_html=True)

    depth = st.slider("Kedalaman (depth)", 1, 3, 2,
                      help="0 = hanya seed. 1 = seed + link-nya. 2 = sampai level 2.")
    max_pages = st.slider("Total halaman maksimum", 10, 100, 30, step=5)
    per_domain = st.slider("Halaman per domain", 1, 10, 3,
                           help="Batas agar satu domain tidak mendominasi hasil.")
    delay = st.slider("Jeda antar request (detik)", 0.2, 3.0, 0.8, step=0.1)
    max_seconds = st.slider("Batas waktu crawl (detik)", 30, 180, 90, step=10)
    respect_robots = st.checkbox("Patuhi robots.txt", value=False,
                                 help="Default nonaktif agar bisa crawl website apapun. Aktifkan untuk crawling sopan ke website besar.")
    restrict_seed = st.checkbox("Batasi ke domain seed", value=False,
                                help="Hanya crawl domain yang sama dengan seed URL.")
    weighted = st.checkbox("Edge weight = jumlah tautan", value=True)
    damping = st.slider("Damping factor PageRank", 0.50, 0.95, 0.85, step=0.01)

    st.markdown("---")
    st.markdown('<div class="section-title">Database</div>', unsafe_allow_html=True)
    show_history = st.checkbox("Tampilkan history crawl", value=False)

# ---------------------------------------------------------------------------
# Input form
# ---------------------------------------------------------------------------
col_input, col_run, col_clear = st.columns([5, 1, 1])
with col_input:
    url_input = st.text_input(
        "URL awal",
        placeholder="https://trunojoyo.ac.id",
        label_visibility="collapsed",
    )
with col_run:
    run = st.button("Jalankan", type="primary", use_container_width=True)
with col_clear:
    if st.button("Reset", use_container_width=True):
        if "result" in st.session_state:
            del st.session_state["result"]
        st.rerun()

st.caption("Contoh: https://trunojoyo.ac.id, https://wikipedia.org, https://github.com")

# ---------------------------------------------------------------------------
# Run analysis
# ---------------------------------------------------------------------------
def run_analysis(url: str):
    norm = normalize_url(url if "://" in url else "https://" + url)
    if not norm:
        st.error("URL tidak valid. Gunakan format http:// atau https://")
        return None

    progress_bar = st.progress(0.0, text="Memulai crawl...")
    status_text = st.empty()

    def on_progress(level, done, total, current):
        pct = done / max(total, 1)
        progress_bar.progress(pct, text=f"Level {level} - {done}/{total} halaman")
        status_text.text(f"Sedang: {current[:80]}")

    crawler = Crawler(
        max_depth=depth,
        max_pages=max_pages,
        per_domain=per_domain,
        delay=delay,
        workers=4,
        respect_robots=respect_robots,
        max_seconds=max_seconds,
        restrict_to_seed_domain=restrict_seed,
        progress=on_progress,
    )

    t0 = time.time()
    crawler.crawl([norm])
    elapsed = time.time() - t0
    progress_bar.empty()
    status_text.empty()

    if not crawler.pages:
        st.error("Tidak ada halaman berhasil di-crawl. Penyebab umum: URL tidak valid, koneksi diblokir, atau robots.txt melarang.")
        return None

    if not crawler.edges:
        st.warning("Halaman terbaca tapi tidak ada tautan keluar ke domain lain. Coba naikkan kedalaman.")

    G = build_graph(crawler, weighted=weighted)
    pr = pagerank(G, damping=damping)
    metrics_df = compute_metrics(G, pr)

    # Simpan ke database
    try:
        save_crawl_result(
            db_path=str(DB_PATH),
            seed_url=norm,
            seed_domain=get_domain(norm),
            elapsed=elapsed,
            params={
                "max_depth": depth, "max_pages": max_pages,
                "per_domain": per_domain, "damping": damping,
            },
            num_pages=len(crawler.pages),
            num_domains=len(crawler.pages_crawled),
            num_edges=G.number_of_edges(),
            top_domain=metrics_df.iloc[0]["node"] if len(metrics_df) > 0 else "",
            top_pagerank=metrics_df.iloc[0]["page_rank"] if len(metrics_df) > 0 else 0.0,
            pages=[
                {
                    "url": p.url, "domain": p.domain, "title": p.title,
                    "depth": p.depth, "out_links_count": len(p.links),
                }
                for p in crawler.pages.values()
            ],
            edges=[
                {"source": s, "target": t, "weight": w}
                for (s, t), w in crawler.edges.items()
            ],
            pageranks=[
                {
                    "domain": row["node"], "page_rank": row["page_rank"],
                    "in_degree": row["in_degree"], "out_degree": row["out_degree"],
                    "ranking": int(row["ranking"]),
                }
                for _, row in metrics_df.iterrows()
            ],
        )
    except Exception as e:
        st.warning(f"Gagal menyimpan ke database: {e}")

    return {
        "url": norm, "seed": get_domain(norm), "G": G, "pr": pr,
        "metrics_df": metrics_df, "crawler": crawler, "elapsed": elapsed,
        "summary": graph_summary(G),
    }


if run:
    if not url_input.strip():
        st.warning("Masukkan URL terlebih dahulu.")
    else:
        with st.spinner("Sedang crawling..."):
            result = run_analysis(url_input.strip())
            st.session_state["result"] = result

# ---------------------------------------------------------------------------
# Tampilkan history crawl
# ---------------------------------------------------------------------------
if show_history:
    st.markdown("---")
    st.markdown('<div class="section-title">History Crawl</div>', unsafe_allow_html=True)
    history_df = list_crawls(str(DB_PATH), limit=20)
    if history_df.empty:
        st.info("Belum ada history crawl.")
    else:
        st.dataframe(
            history_df[["id", "seed_url", "started_at", "elapsed_seconds",
                        "num_pages", "num_domains", "num_edges", "top_domain"]],
            hide_index=True,
            use_container_width=True,
        )

# ---------------------------------------------------------------------------
# Tampilkan hasil
# ---------------------------------------------------------------------------
res = st.session_state.get("result")
if not res:
    st.info("Masukkan URL dan tekan Jalankan untuk memulai analisis.")
    st.stop()

G, pr, seed = res["G"], res["pr"], res["seed"]
metrics_df = res["metrics_df"]
summary = res["summary"]
crawler = res["crawler"]
elapsed = res["elapsed"]

# Stat cards
top_site = metrics_df.iloc[0]["node"] if len(metrics_df) > 0 else "-"
top_score = metrics_df.iloc[0]["page_rank"] if len(metrics_df) > 0 else 0

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""
    <div class="stat-card">
      <div class="stat-label">Domain Ditemukan</div>
      <div class="stat-value">{summary["nodes"]}</div>
    </div>
    """, unsafe_allow_html=True)
with c2:
    st.markdown(f"""
    <div class="stat-card">
      <div class="stat-label">Halaman Di-crawl</div>
      <div class="stat-value">{len(crawler.pages)}</div>
    </div>
    """, unsafe_allow_html=True)
with c3:
    st.markdown(f"""
    <div class="stat-card">
      <div class="stat-label">Edge Antar Domain</div>
      <div class="stat-value">{summary["edges"]}</div>
    </div>
    """, unsafe_allow_html=True)
with c4:
    st.markdown(f"""
    <div class="stat-card">
      <div class="stat-label">Domain Terpenting</div>
      <div class="stat-value small">{top_site}</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# Tabs
tab_graph, tab_rank, tab_metrics, tab_export = st.tabs([
    "Graf Interaktif",
    "Peringkat PageRank",
    "Metrik Graph",
    "Export Data",
])

# --- Tab 1: Graf Interaktif ---
with tab_graph:
    n_total = G.number_of_nodes()
    top_n_default = min(30, n_total) if n_total > 0 else 10
    if n_total > 5:
        col_slider, col_info = st.columns([3, 2])
        with col_slider:
            top_n = st.slider(
                "Jumlah node ditampilkan (top PageRank)",
                5, max(5, n_total), top_n_default,
                help="Node dengan PageRank tertinggi akan ditampilkan. Node kuning = seed."
            )
        with col_info:
            st.caption(f"Total domain ditemukan: {n_total} - menampilkan top {top_n}")
    else:
        top_n = n_total
        st.caption(f"Total domain: {n_total}")

    # Build pyvis network (force-directed, mirip citationgraph.org)
    from pyvis.network import Network

    keep_nodes = {row["node"] for _, row in metrics_df.head(top_n).iterrows()} | {seed}
    H = G.subgraph(keep_nodes).copy()

    if H.number_of_nodes() > 0:
        pr_max = max(pr[n] for n in H) or 1.0
        pr_min = min(pr[n] for n in H)

        net = Network(
            height="650px",
            width="100%",
            directed=True,
            bgcolor="#0b0f17" if st.session_state["theme_dark"] else "#fafafa",
            font_color="#e6edf3" if st.session_state["theme_dark"] else "#0f172a",
            cdn_resources="in_line",
            notebook=False,
            select_menu=False,
            filter_menu=False,
        )

        # Warna gradien biru (semua node biru dengan intensitas berbeda),
        # node seed = kuning untuk highlight
        for node in H.nodes():
            t = (pr[node] - pr_min) / (pr_max - pr_min) if pr_max > pr_min else 0.5
            is_seed = node == seed

            if is_seed:
                color = {
                    "background": "#fbbf24",
                    "border": "#f59e0b",
                    "highlight": {"background": "#fbbf24", "border": "#d97706"},
                }
                border_width = 3
                size = 25 + 25 * t
            else:
                # Gradient biru muda -> biru tua berdasarkan PageRank
                if st.session_state["theme_dark"]:
                    r = int(96 - 50 * t)
                    g = int(165 - 80 * t)
                    b = int(250 - 30 * t)
                    border = "#1f2937"
                else:
                    r = int(59 + 80 * t)
                    g = int(130 - 50 * t)
                    b = int(246 - 80 * t)
                    border = "#cbd5e1"
                color = {
                    "background": f"rgb({r}, {g}, {b})",
                    "border": border,
                    "highlight": {"background": f"rgb({r}, {g}, {b})", "border": border},
                }
                border_width = 1
                size = 12 + 30 * t

            # In-degree dan out-degree untuk tooltip
            in_deg = H.in_degree(node)
            out_deg = H.out_degree(node)

            net.add_node(
                node,
                label=node,
                size=size,
                color=color,
                borderWidth=border_width,
                title=(
                    f"Domain: {node}\n"
                    f"PageRank: {pr[node]:.5f}\n"
                    f"In-degree: {in_deg}\n"
                    f"Out-degree: {out_deg}"
                ),
                font={"size": 12, "face": "Inter, -apple-system, sans-serif"},
            )

        # Edge dengan weight, warna halus
        max_weight = max((d.get("weight", 1) for _, _, d in H.edges(data=True)), default=1)
        for u, v, d in H.edges(data=True):
            w = d.get("weight", 1)
            # Lebar edge proporsional terhadap weight
            width_val = max(0.5, min(3, 1 + 2 * (w / max_weight)))
            net.add_edge(
                u, v,
                value=w,
                width=width_val,
                color={"color": "rgba(148,163,184,0.35)", "highlight": "rgba(148,163,184,0.7)"},
                title=f"{u} -> {v}\nWeight: {w}",
                arrows={"to": {"enabled": True, "scaleFactor": 0.5}},
            )

        # Options: force-directed layout, smooth edges, hover highlight
        net.set_options("""{
          "interaction": {
            "hover": true,
            "tooltipDelay": 80,
            "navigationButtons": true,
            "zoomView": true,
            "dragView": true,
            "dragNodes": true,
            "multiselect": false
          },
          "physics": {
            "solver": "forceAtlas2Based",
            "forceAtlas2Based": {
              "gravitationalConstant": -55,
              "centralGravity": 0.01,
              "springLength": 130,
              "springConstant": 0.08,
              "damping": 0.4,
              "avoidOverlap": 0.5
            },
            "stabilization": {
              "enabled": true,
              "iterations": 300,
              "updateInterval": 25,
              "onlyDynamicEdges": false,
              "fit": true
            },
            "timestep": 0.5,
            "maxVelocity": 50
          },
          "configure": {
            "enabled": false
          },
          "edges": {
            "smooth": {"type": "continuous", "roundness": 0.5},
            "color": {"inherit": false},
            "scaling": {"min": 0.5, "max": 3}
          },
          "nodes": {
            "shape": "dot",
            "scaling": {"min": 10, "max": 50}
          }
        }""")

        import streamlit.components.v1 as components
        components.html(net.generate_html(notebook=False), height=680, scrolling=True)

        st.caption(
            "Node kuning = seed domain. Ukuran node proporsional terhadap PageRank. "
            "Lebar edge proporsional terhadap jumlah tautan antar domain. "
            "Scroll untuk zoom, drag untuk geser, hover untuk detail."
        )
    else:
        st.info("Tidak ada node untuk ditampilkan.")

# --- Tab 2: Peringkat PageRank ---
with tab_rank:
    c_left, c_right = st.columns([2, 1])
    with c_left:
        st.markdown('<div class="section-title">Top PageRank</div>', unsafe_allow_html=True)
        st.dataframe(
            metrics_df[["ranking", "node", "page_rank", "in_degree", "out_degree"]].head(20),
            hide_index=True,
            use_container_width=True,
            column_config={
                "page_rank": st.column_config.ProgressColumn(
                    "page_rank", format="%.5f",
                    min_value=0, max_value=float(metrics_df["page_rank"].max()) or 1.0,
                )
            }
        )
    with c_right:
        st.markdown('<div class="section-title">Top 10 Bar Chart</div>', unsafe_allow_html=True)
        top10 = metrics_df.head(10).set_index("node")["page_rank"]
        st.bar_chart(top10, horizontal=True)

    st.success(f"**{top_site}** memiliki PageRank tertinggi ({top_score:.5f}) karena banyak ditauni oleh domain lain yang juga penting.")

# --- Tab 3: Metrik Graph ---
with tab_metrics:
    st.markdown('<div class="section-title">Ringkasan Graph</div>', unsafe_allow_html=True)
    metric_rows = [
        ("Jumlah node (domain)", summary["nodes"]),
        ("Jumlah edge", summary["edges"]),
        ("Density", summary["density"]),
        ("Graf berarah", "Ya" if summary["is_directed"] else "Tidak"),
        ("Strongly connected", "Ya" if summary["is_strongly_connected"] else "Tidak"),
    ]
    if summary.get("diameter") is not None:
        metric_rows.append(("Diameter", summary["diameter"]))
    if summary.get("average_shortest_path") is not None:
        metric_rows.append(("Rata-rata shortest path", summary["average_shortest_path"]))

    metric_df = pd.DataFrame(metric_rows, columns=["Metrik", "Nilai"])
    st.dataframe(metric_df, hide_index=True, use_container_width=True)

    st.markdown('<div class="section-title">Distribusi Derajat</div>', unsafe_allow_html=True)
    dist_c1, dist_c2 = st.columns(2)
    with dist_c1:
        st.markdown("**Distribusi In-degree**")
        in_dist = metrics_df["in_degree"].value_counts().sort_index()
        st.bar_chart(in_dist)
    with dist_c2:
        st.markdown("**Distribusi Out-degree**")
        out_dist = metrics_df["out_degree"].value_counts().sort_index()
        st.bar_chart(out_dist)

    st.markdown('<div class="section-title">Detail Crawl</div>', unsafe_allow_html=True)
    detail_rows = [
        ("Seed URL", res["url"]),
        ("Seed domain", seed),
        ("Waktu crawl", f"{elapsed:.2f} detik"),
        ("Halaman di-crawl per domain", str(dict(crawler.pages_crawled))),
    ]
    detail_df = pd.DataFrame(detail_rows, columns=["Item", "Nilai"])
    st.dataframe(detail_df, hide_index=True, use_container_width=True)

# --- Tab 4: Export ---
with tab_export:
    st.markdown('<div class="section-title">Download Hasil</div>', unsafe_allow_html=True)
    st.write("Sistem akan otomatis menyimpan hasil ke folder `exports/` dengan beberapa format.")

    if st.button("Generate file export", type="primary"):
        with st.spinner("Mengekspor..."):
            export_paths = export_graph(G, pr, str(EXPORT_DIR), prefix=f"crawl_{int(time.time())}")
            st.success("Export berhasil!")
            for fmt, path in export_paths.items():
                with open(path, "rb") as f:
                    data = f.read()
                ext = Path(path).suffix[1:]
                st.download_button(
                    label=f"Download {fmt.upper()} ({ext})",
                    data=data,
                    file_name=Path(path).name,
                    mime="application/octet-stream",
                    key=f"dl_{fmt}",
                )

    st.markdown("---")
    st.markdown('<div class="section-title">Quick CSV Export</div>', unsafe_allow_html=True)
    col_csv1, col_csv2 = st.columns(2)
    with col_csv1:
        st.download_button(
            "Download PageRank CSV",
            data=metrics_df.to_csv(index=False).encode("utf-8"),
            file_name="pagerank.csv",
            mime="text/csv",
        )
    with col_csv2:
        edges_df = pd.DataFrame([
            {"source": u, "target": v, "weight": d.get("weight", 1)}
            for u, v, d in G.edges(data=True)
        ])
        st.download_button(
            "Download Edges CSV",
            data=edges_df.to_csv(index=False).encode("utf-8"),
            file_name="edges.csv",
            mime="text/csv",
        )

# Footer
st.markdown("""
<div class="footer">
  Web Crawler & PageRank Analyzer - Tugas Web Structure Mining
</div>
""", unsafe_allow_html=True)
