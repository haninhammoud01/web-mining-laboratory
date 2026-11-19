"""
Streamlit app: Web Crawler + PageRank antarwebsite.
Jalankan lokal:  streamlit run app.py

Tema: Black + Pink (minimalis, professional, mirip Vercel/GitHub Copilot).
Menggunakan pyvis (vis.js) untuk visualisasi graph live dan interaktif.
Tanpa toggle dark/light - gunakan tema bawaan Streamlit (Settings browser).
"""

from __future__ import annotations

import os
import sys
import time
from collections import defaultdict
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
    page_title="WebRank Explorer",
    page_icon="🕸️",
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
# Tema Black-Pink (hardcoded, tidak ada toggle)
# Pink accent: #ec4899 (Pink-500)
# ---------------------------------------------------------------------------
PINK = "#ec4899"
PINK_LIGHT = "#f472b6"
PINK_DARK = "#be185d"

st.markdown("""
<style>
/* === GLOBAL === */
.stApp {
    background-color: #09090b;
    color: #fafafa;
}

/* === SIDEBAR === */
.stSidebar, .stSidebar > div {
    background-color: #0c0c0f;
    border-right: 1px solid #1f1f23;
}
.stSidebar h1, .stSidebar h2, .stSidebar h3, .stSidebar h4 {
    color: #fafafa;
    font-weight: 600;
    letter-spacing: -0.01em;
}

/* Section heading di sidebar - mirip dokumentasi Vercel */
.sidebar-heading {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #71717a;
    margin: 1.5rem 0 0.5rem 0;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid #1f1f23;
}

/* === MAIN CONTENT === */
.block-container {
    padding-top: 2rem;
    max-width: 1300px;
}

/* === HERO === */
.hero {
    padding: 2.2rem 2.4rem;
    margin-bottom: 1.5rem;
    background: #0c0c0f;
    border: 1px solid #1f1f23;
    border-radius: 12px;
    border-left: 3px solid #ec4899;
}
.hero h1 {
    margin: 0 0 0.6rem 0;
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #fafafa;
}
.hero h1 .accent {
    color: #ec4899;
}
.hero p {
    margin: 0;
    color: #a1a1aa;
    font-size: 0.95rem;
    max-width: 720px;
    line-height: 1.5;
}

/* === SECTION HEADING (uppercase kecil, mirip Vercel docs) === */
.section-heading {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #71717a;
    margin: 1.5rem 0 0.8rem 0;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid #1f1f23;
}

/* === STAT CARDS (icon mini + value) === */
.stat-card {
    background: #0c0c0f;
    border: 1px solid #1f1f23;
    border-radius: 8px;
    padding: 1.1rem 1.2rem;
    display: flex;
    align-items: center;
    gap: 0.9rem;
    height: 100%;
    transition: border-color 0.15s ease;
}
.stat-card:hover {
    border-color: #ec4899;
}
.stat-card .icon {
    width: 36px;
    height: 36px;
    border-radius: 6px;
    background: rgba(236, 72, 153, 0.1);
    border: 1px solid rgba(236, 72, 153, 0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    color: #ec4899;
    flex-shrink: 0;
}
.stat-card .content {
    flex: 1;
    min-width: 0;
}
.stat-card .label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #71717a;
    margin-bottom: 0.2rem;
}
.stat-card .value {
    font-size: 1.4rem;
    font-weight: 700;
    color: #fafafa;
    line-height: 1.2;
    word-break: break-all;
}
.stat-card .value.small {
    font-size: 0.95rem;
    font-weight: 600;
}

/* === PILLS === */
.pill {
    display: inline-block;
    padding: 0.18rem 0.65rem;
    border-radius: 999px;
    margin: 0 0.25rem 0.25rem 0;
    background: rgba(236, 72, 153, 0.08);
    border: 1px solid rgba(236, 72, 153, 0.25);
    font-size: 0.78rem;
    color: #fafafa;
    transition: all 0.15s ease;
}
.pill:hover {
    background: rgba(236, 72, 153, 0.15);
    border-color: rgba(236, 72, 153, 0.5);
}

/* === PRIMARY BUTTON (pink accent) === */
div.stButton > button[kind="primary"] {
    background-color: #ec4899;
    color: white;
    border: 0;
    font-weight: 600;
    border-radius: 8px;
    padding: 0.55rem 1.4rem;
    transition: background-color 0.15s ease;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #be185d;
}

/* === INPUT === */
.stTextInput > div > div > input {
    background-color: #0c0c0f !important;
    color: #fafafa !important;
    border: 1px solid #27272a !important;
    border-radius: 8px !important;
    font-family: inherit !important;
}
.stTextInput > div > div > input:focus {
    border-color: #ec4899 !important;
    box-shadow: 0 0 0 3px rgba(236, 72, 153, 0.1) !important;
}

/* === SLIDER === */
.stSlider > div > div > div > div {
    background-color: #ec4899 !important;
}

/* === TABS - underline pink === */
.stTabs [data-baseweb="tab-list"] {
    background-color: transparent;
    border-bottom: 1px solid #27272a;
    gap: 0;
}
.stTabs [data-baseweb="tab"] {
    color: #71717a;
    font-weight: 500;
    padding: 0.6rem 1rem;
    border-radius: 0;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #fafafa;
}
.stTabs [aria-selected="true"] {
    color: #fafafa !important;
    background-color: transparent !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    background-color: #ec4899 !important;
    height: 2px !important;
}
.stTabs [data-baseweb="tab-border"] {
    border: 0 !important;
}

/* === DATAFRAME === */
.stDataFrame [data-baseweb="table"] {
    background-color: #0c0c0f;
}
.stDataFrame [data-baseweb="table"] thead {
    background-color: #18181b;
}
.stDataFrame [data-baseweb="table"] th {
    color: #a1a1aa;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
}

/* === EXPANDER === */
.streamlit-expanderHeader {
    background-color: #0c0c0f;
    color: #fafafa;
    font-size: 0.85rem;
    border: 1px solid #27272a;
    border-radius: 6px;
}

/* === TEXT COLOR === */
h1, h2, h3, h4, h5, h6 { color: #fafafa !important; }
p, li, span { color: #d4d4d8; }
strong { color: #fafafa; }
a { color: #ec4899; text-decoration: none; }
a:hover { color: #f472b6; text-decoration: underline; }

/* === SUCCESS / WARNING / ERROR === */
.stAlert > div {
    background-color: #0c0c0f !important;
    border: 1px solid #27272a !important;
}

/* === CAPTION === */
.stCaption {
    color: #71717a !important;
    font-size: 0.8rem !important;
}

/* === DIVIDER === */
hr {
    border-color: #1f1f23 !important;
    margin: 2rem 0 !important;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Hero section (minimalis: logo web + judul saja yang ada emoji)
# ---------------------------------------------------------------------------
st.markdown(
    """
<div class="hero">
  <h1>🕸️ <span class="accent">WebRank Explorer</span></h1>
  <p>Masukkan sebuah link website. Aplikasi akan menelusuri tautan-tautannya, membangun graph
  keterhubungan antarwebsite, lalu menghitung PageRank untuk menemukan website paling berpengaruh.</p>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar: pengaturan (tanpa emoji, hanya heading uppercase kecil)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="sidebar-heading">Pengaturan Crawl</div>', unsafe_allow_html=True)
    depth = st.slider("Kedalaman (depth)", 1, 3, 2,
                      help="Seberapa jauh tautan diikuti. Makin dalam makin lama.")
    max_pages = st.slider("Maks. total halaman", 10, 150, 50, step=10)
    per_domain = st.slider("Maks. halaman per website", 1, 15, 5)
    delay = st.slider("Jeda antar request (detik)", 0.2, 3.0, 0.5, step=0.1,
                      help="Jeda sopan terhadap website yang sama.")
    max_seconds = st.slider("Batas waktu crawl (detik)", 20, 300, 90, step=10)
    respect_robots = st.checkbox("Patuhi robots.txt", value=False,
                                 help="Default nonaktif agar bisa crawl website apapun.")
    weighted = st.checkbox("Bobot edge = jumlah tautan", value=True)
    damping = st.slider("Damping factor PageRank", 0.50, 0.99, 0.85, step=0.01)
    restrict_seed = st.checkbox("Batasi ke domain seed", value=False,
                                help="Hanya crawl domain yang sama dengan seed URL.")

    st.markdown('<div class="sidebar-heading">Database</div>', unsafe_allow_html=True)
    show_history = st.checkbox("Tampilkan history crawl", value=False)

# ---------------------------------------------------------------------------
# Input section
# ---------------------------------------------------------------------------
st.markdown('<div class="section-heading">URL Analisis</div>', unsafe_allow_html=True)

c_in, c_btn = st.columns([5, 1], vertical_alignment="bottom")
with c_in:
    url_input = st.text_input("Link website", placeholder="https://www.wikipedia.org",
                              label_visibility="collapsed")
with c_btn:
    run = st.button("Analisis", type="primary", use_container_width=True)

st.caption("Contoh: https://www.wikipedia.org - https://news.ycombinator.com - https://github.com - https://trunojoyo.ac.id")

# ---------------------------------------------------------------------------
# Proses crawl
# ---------------------------------------------------------------------------
def run_analysis(url):
    norm = normalize_url(url if "://" in url else "https://" + url)
    if not norm:
        st.error("Link tidak valid. Gunakan format http:// atau https://")
        return None

    bar = st.progress(0.0, text="Memulai crawl...")
    status_text = st.empty()

    def on_progress(level, done, total, current):
        bar.progress(done / max(total, 1),
                     text=f"Level {level}/{depth} - {done}/{total} halaman")
        status_text.text(f"Sedang: {current[:80]}")

    crawler = Crawler(max_depth=depth, max_pages=max_pages, per_domain=per_domain,
                      delay=delay, workers=8, respect_robots=respect_robots,
                      max_seconds=max_seconds, restrict_to_seed_domain=restrict_seed,
                      progress=on_progress)
    t0 = time.time()
    crawler.crawl([norm])
    elapsed = time.time() - t0
    bar.empty()
    status_text.empty()

    if not crawler.pages_crawled:
        st.error("Tidak ada halaman yang berhasil dibaca. Penyebab umum: website memblokir bot, "
                 "dilarang robots.txt, bukan halaman HTML, atau alamat tidak dapat dijangkau.")
        return None
    if not crawler.edges:
        st.warning("Halaman terbaca, tetapi tidak ditemukan tautan ke website lain.")
        return None

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
                {"url": p.url, "domain": p.domain, "title": p.title,
                 "depth": p.depth, "out_links_count": len(p.links)}
                for p in crawler.pages.values()
            ],
            edges=[
                {"source": s, "target": t, "weight": w}
                for (s, t), w in crawler.edges.items()
            ],
            pageranks=[
                {"domain": row["node"], "page_rank": row["page_rank"],
                 "in_degree": row["in_degree"], "out_degree": row["out_degree"],
                 "ranking": int(row["ranking"])}
                for _, row in metrics_df.iterrows()
            ],
        )
    except Exception as e:
        st.warning(f"Gagal simpan ke database: {e}")

    return {"url": norm, "seed": get_domain(norm), "G": G, "pr": pr,
            "elapsed": elapsed, "metrics_df": metrics_df,
            "edges": dict(crawler.edges), "page_links": list(crawler.page_links),
            "titles": dict(crawler.page_titles), "crawled": dict(crawler.pages_crawled),
            "crawler": crawler}


if run:
    if not url_input.strip():
        st.warning("Masukkan link terlebih dahulu.")
    else:
        with st.spinner("Sedang crawling..."):
            result = run_analysis(url_input.strip())
            st.session_state["result"] = result

# Tampilkan history crawl
if show_history:
    st.markdown('<div class="section-heading">History Crawl</div>', unsafe_allow_html=True)
    history_df = list_crawls(str(DB_PATH), limit=20)
    if history_df.empty:
        st.info("Belum ada history crawl.")
    else:
        st.dataframe(
            history_df[["id", "seed_url", "started_at", "elapsed_seconds",
                        "num_pages", "num_domains", "num_edges", "top_domain"]],
            hide_index=True, use_container_width=True,
        )

# ---------------------------------------------------------------------------
# Tampilkan hasil
# ---------------------------------------------------------------------------
res = st.session_state.get("result")
if not res:
    st.info("Masukkan link lalu tekan Analisis untuk memulai.")
    st.stop()

G, pr, seed = res["G"], res["pr"], res["seed"]
metrics_df = res["metrics_df"]
crawler = res["crawler"]
ranking = sorted(pr.items(), key=lambda x: -x[1])
top_site, top_score = ranking[0]
elapsed = res["elapsed"]

# ---------------------------------------------------------------------------
# Stat cards (icon mini + value, minimalis, tanpa emoji di label)
# ---------------------------------------------------------------------------
st.markdown('<div class="section-heading">Ringkasan</div>', unsafe_allow_html=True)

def stat_card(col, icon, label, value, small=False):
    col.markdown(f"""
    <div class="stat-card">
      <div class="icon">{icon}</div>
      <div class="content">
        <div class="label">{label}</div>
        <div class="value {"small" if small else ""}">{value}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

m = st.columns(4)
stat_card(m[0], "🌐", "Website ditemukan", f"{G.number_of_nodes():,}")
stat_card(m[1], "📄", "Halaman di-crawl", f"{sum(res['crawled'].values()):,}")
stat_card(m[2], "🔗", "Tautan antarwebsite", f"{G.number_of_edges():,}")
stat_card(m[3], "★", "Paling penting", top_site, small=True)
st.write("")

# ---------------------------------------------------------------------------
# Tabs (tanpa emoji di label, hanya teks)
# ---------------------------------------------------------------------------
tab_graph, tab_rank, tab_rel, tab_metrics, tab_dl = st.tabs([
    "Graph",
    "Peringkat PageRank",
    "Website Terkait",
    "Metrik Graph",
    "Unduh",
])

# --------------------------------------------------------------------------
# Tab 1: Graph (pakai pyvis = vis.js, live & interaktif)
# Pink + multi-color gradient untuk node
# --------------------------------------------------------------------------
def lerp_color_pink_multicolor(t):
    """Gradient multi-stop: indigo -> purple -> pink -> orange (PageRank rendah -> tinggi).

    Node seed pakai pink solid, node lain pakai gradient ini berdasarkan PageRank.
    """
    # Stops warna-warni tapi tetap dalam tema dark
    stops = [
        (0.0, (99, 102, 241)),    # Indigo-500 (PageRank rendah)
        (0.33, (168, 85, 247)),   # Purple-500
        (0.66, (236, 72, 153)),   # Pink-500
        (1.0, (251, 146, 60)),    # Orange-400 (PageRank tinggi)
    ]
    t = max(0.0, min(1.0, t))
    for i in range(len(stops) - 1):
        t0, (r0, g0, b0) = stops[i]
        t1, (r1, g1, b1) = stops[i + 1]
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0)
            r = int(r0 + (r1 - r0) * f)
            g = int(g0 + (g1 - g0) * f)
            b = int(b0 + (b1 - b0) * f)
            return f"rgb({r}, {g}, {b})"
    return "rgb(99, 102, 241)"


def build_html(G, pr, seed, top_n):
    """Build interactive HTML graph menggunakan pyvis (vis.js).

    Tema: black background, node warna-warni (indigo -> pink -> orange),
    seed = pink solid. vis.js physics otomatis jalan live saat HTML load.
    """
    from pyvis.network import Network
    keep = {n for n, _ in sorted(pr.items(), key=lambda x: -x[1])[:top_n]} | {seed}
    H = G.subgraph(keep)
    vmax, vmin = max(pr[n] for n in H), min(pr[n] for n in H)
    span = (vmax - vmin) or 1

    net = Network(height="640px", width="100%", directed=True,
                  bgcolor="#09090b", font_color="#fafafa",
                  cdn_resources="in_line", notebook=False)

    for n in H.nodes():
        t = (pr[n] - vmin) / span
        is_seed = n == seed
        if is_seed:
            # Seed: pink solid, lebih besar
            color = {"background": "#ec4899", "border": "#ffffff",
                     "highlight": {"background": "#f472b6", "border": "#ffffff"}}
            size = 30
            border_width = 3
        else:
            # Node lain: gradient multi-color
            color_hex = lerp_color_pink_multicolor(t)
            color = {"background": color_hex, "border": "#27272a",
                     "highlight": {"background": color_hex, "border": "#ec4899"}}
            size = 14 + 30 * t
            border_width = 1

        title = (f"<div style='padding:6px;font-family:Inter,sans-serif;'>"
                 f"<b style='font-size:13px;color:#fafafa;'>{n}</b><br>"
                 f"<span style='color:#71717a;'>PageRank:</span> "
                 f"<b style='color:#ec4899;'>{pr[n]:.5f}</b><br>"
                 f"<span style='color:#71717a;'>In-degree:</span> {H.in_degree(n)}<br>"
                 f"<span style='color:#71717a;'>Out-degree:</span> {H.out_degree(n)}"
                 f"</div>")

        net.add_node(n, label=n, size=size, color=color, borderWidth=border_width,
                     title=title,
                     font={"size": 14 if is_seed else 12, "color": "#fafafa",
                           "face": "Inter, -apple-system, sans-serif"})

    for u, v, d in H.edges(data=True):
        weight = d.get("weight", 1)
        net.add_edge(u, v, value=weight,
                     color={"color": "rgba(236, 72, 153, 0.25)",
                            "highlight": "#ec4899"},
                     title=f"{u} → {v}<br>Jumlah tautan: {weight}")

    # Physics: forceAtlas2Based dengan parameter halus & stabil
    # - maxVelocity rendah: node bergerak lambat, tidak pusing
    # - damping tinggi: node cepat tenang setelah bergerak
    # - gravitationalConstant lembut: tidak terlalu kuat tolak-menolak
    # - fit: false supaya tidak auto-rezoom setiap iterasi (yang bikin pusing)
    net.set_options("""{
      "interaction": {
        "hover": true,
        "tooltipDelay": 80,
        "navigationButtons": true,
        "zoomView": true,
        "dragView": true,
        "dragNodes": true,
        "hideEdgesOnDrag": false,
        "hideNodesOnDrag": false
      },
      "physics": {
        "enabled": true,
        "solver": "forceAtlas2Based",
        "forceAtlas2Based": {
          "gravitationalConstant": -35,
          "centralGravity": 0.02,
          "springLength": 130,
          "springConstant": 0.05,
          "damping": 0.6,
          "avoidOverlap": 0.7
        },
        "stabilization": {
          "enabled": true,
          "iterations": 300,
          "updateInterval": 50,
          "onlyDynamicEdges": false,
          "fit": false
        },
        "timestep": 0.3,
        "maxVelocity": 15,
        "adaptiveTimestep": true
      },
      "edges": {
        "smooth": {"type": "continuous", "roundness": 0.5},
        "arrows": {"to": {"enabled": true, "scaleFactor": 0.6}},
        "color": {"inherit": false},
        "scaling": {"min": 1, "max": 5}
      },
      "nodes": {
        "shape": "dot",
        "scaling": {"min": 10, "max": 50}
      }
    }""")
    return net.generate_html(notebook=False)


with tab_graph:
    n_total = G.number_of_nodes()
    top_n = n_total if n_total <= 10 else st.slider(
        "Jumlah website ditampilkan (berdasarkan PageRank tertinggi)",
        5, n_total, min(n_total, 40)
    )
    import streamlit.components.v1 as components

    components.html(
        build_html(G, pr, seed, top_n),
        width=None,
        height=660,
        scrolling=True
    )
    st.caption("Node pink = website awal (seed). Ukuran & warna node = PageRank. "
               "Anak panah = arah tautan. Scroll untuk zoom, seret untuk menggeser.")

# --------------------------------------------------------------------------
# Tab 2: Peringkat PageRank
# --------------------------------------------------------------------------
df_rank = pd.DataFrame([
    {"Peringkat": i, "Website": s, "PageRank": sc, "Tautan masuk": G.in_degree(s),
     "Tautan keluar": G.out_degree(s), "Halaman di-crawl": res["crawled"].get(s, 0)}
    for i, (s, sc) in enumerate(ranking, 1)
])

with tab_rank:
    left, right = st.columns([3, 2])
    with left:
        st.dataframe(
            df_rank, hide_index=True, use_container_width=True, height=470,
            column_config={
                "PageRank": st.column_config.ProgressColumn(
                    "PageRank", format="%.5f",
                    min_value=0, max_value=float(df_rank["PageRank"].max())),
            }
        )
    with right:
        st.markdown('<div class="section-heading">Top 10 Website</div>', unsafe_allow_html=True)
        st.bar_chart(df_rank.head(10).set_index("Website")["PageRank"],
                     horizontal=True, color="#ec4899")
    st.success(f"{top_site} adalah website dengan tingkat kepentingan tertinggi "
               f"(PageRank {top_score:.5f}), karena banyak menerima tautan dari website penting lain.")

# --------------------------------------------------------------------------
# Tab 3: Website Terkait
# --------------------------------------------------------------------------
with tab_rel:
    st.markdown(f'<div class="section-heading">Website Terkait dengan {seed}</div>', unsafe_allow_html=True)
    out_nb = sorted(G.successors(seed), key=lambda n: -pr[n]) if seed in G else []
    in_nb = sorted(G.predecessors(seed), key=lambda n: -pr[n]) if seed in G else []

    a, b = st.columns(2)
    with a:
        st.markdown(f"**Ditautkan oleh {seed}** ({len(out_nb)})")
        if out_nb:
            st.markdown("".join(f'<span class="pill">{n}</span>' for n in out_nb[:30]),
                        unsafe_allow_html=True)
        else:
            st.caption("Tidak ada.")
    with b:
        st.markdown(f"**Menaut ke {seed}** ({len(in_nb)})")
        if in_nb:
            st.markdown("".join(f'<span class="pill">{n}</span>' for n in in_nb[:30]),
                        unsafe_allow_html=True)
        else:
            st.caption("Tidak ditemukan pada crawl ini.")

    st.markdown('<div class="section-heading">Rincian Tautan dari Website Awal</div>', unsafe_allow_html=True)
    by_dst = defaultdict(list)
    for src_url, dst_url in res["page_links"]:
        if get_domain(src_url) == seed and get_domain(dst_url) != seed:
            by_dst[get_domain(dst_url)].append((src_url, dst_url))
    if not by_dst:
        st.caption("Tidak ada tautan keluar dari website awal.")
    for dst in sorted(by_dst, key=lambda n: -pr.get(n, 0)):
        pairs = by_dst[dst]
        with st.expander(f"{dst} - {len(pairs)} tautan - PageRank {pr.get(dst, 0):.5f}"):
            for src_url, dst_url in pairs[:15]:
                title = res["titles"].get(src_url) or src_url
                st.markdown(f"- {dst_url}  \n  dari: {title}")
            if len(pairs) > 15:
                st.caption(f"... dan {len(pairs) - 15} tautan lainnya")

# --------------------------------------------------------------------------
# Tab 4: Metrik Graph
# --------------------------------------------------------------------------
with tab_metrics:
    summary = graph_summary(G)
    st.markdown('<div class="section-heading">Ringkasan Graph</div>', unsafe_allow_html=True)
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

    st.markdown('<div class="section-heading">Distribusi Derajat</div>', unsafe_allow_html=True)
    dist_c1, dist_c2 = st.columns(2)
    with dist_c1:
        st.markdown("**Distribusi In-degree**")
        in_dist = pd.Series([d for _, d in G.in_degree()]).value_counts().sort_index()
        st.bar_chart(in_dist, color="#ec4899")
    with dist_c2:
        st.markdown("**Distribusi Out-degree**")
        out_dist = pd.Series([d for _, d in G.out_degree()]).value_counts().sort_index()
        st.bar_chart(out_dist, color="#ec4899")

    st.markdown('<div class="section-heading">Detail Crawl</div>', unsafe_allow_html=True)
    detail_rows = [
        ("Seed URL", res["url"]),
        ("Seed domain", seed),
        ("Waktu crawl", f"{elapsed:.2f} detik"),
        ("Halaman di-crawl per domain", str(dict(crawler.pages_crawled))),
    ]
    detail_df = pd.DataFrame(detail_rows, columns=["Item", "Nilai"])
    st.dataframe(detail_df, hide_index=True, use_container_width=True)

# --------------------------------------------------------------------------
# Tab 5: Unduh
# --------------------------------------------------------------------------
with tab_dl:
    df_edges = pd.DataFrame(
        [{"sumber": u, "tujuan": v, "jumlah_tautan": c} for (u, v), c in res["edges"].items()]
    ).sort_values("jumlah_tautan", ascending=False)

    st.markdown('<div class="section-heading">Download Hasil Analisis</div>', unsafe_allow_html=True)

    d1, d2 = st.columns(2)
    with d1:
        st.download_button("pagerank.csv",
                           df_rank.to_csv(index=False).encode("utf-8"),
                           "pagerank.csv", "text/csv", use_container_width=True)
    with d2:
        st.download_button("edges.csv",
                           df_edges.to_csv(index=False).encode("utf-8"),
                           "edges.csv", "text/csv", use_container_width=True)

    st.markdown('<div class="section-heading">Export ke Format Lain</div>', unsafe_allow_html=True)

    if st.button("Generate file export (GraphML, JSON)", type="primary"):
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

    st.caption(f"Crawl selesai dalam {elapsed:.1f} detik - seed: {res['url']}")
