"""
Streamlit app: Web Crawler + PageRank antarwebsite.
Jalankan lokal:  streamlit run app.py

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
from flourish_graph import render_flourish_graph

# ---------------------------------------------------------------------------
# Konfigurasi halaman
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Web Crawler PageRank Analyzer",
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
# Tema & styling - palet teal-emerald (BEDA dari referensi ungu-pink)
# ---------------------------------------------------------------------------
def apply_theme(dark: bool) -> None:
    """Apply dark/light theme via custom CSS dengan palet teal-emerald."""
    if dark:
        # Dark mode: deep teal background
        hero_grad_start = "#0d9488"   # Teal-600
        hero_grad_mid = "#059669"     # Emerald-600
        hero_grad_end = "#10b981"     # Emerald-500
        bg = "#0a0e17"
        surface = "#0f172a"
        surface_alt = "rgba(20, 184, 166, 0.08)"  # Teal translucent
        border = "rgba(20, 184, 166, 0.25)"
        text = "#e2e8f0"
        text_muted = "#94a3b8"
        accent = "#14b8a6"
        pill_bg = "rgba(20, 184, 166, 0.15)"
        pill_border = "rgba(20, 184, 166, 0.45)"
        btn_grad_start = "#0d9488"
        btn_grad_end = "#10b981"
    else:
        # Light mode: bright emerald
        hero_grad_start = "#0d9488"
        hero_grad_mid = "#10b981"
        hero_grad_end = "#34d399"
        bg = "#ffffff"
        surface = "#f8fafc"
        surface_alt = "rgba(20, 184, 166, 0.06)"
        border = "rgba(20, 184, 166, 0.2)"
        text = "#0f172a"
        text_muted = "#64748b"
        accent = "#0d9488"
        pill_bg = "rgba(20, 184, 166, 0.12)"
        pill_border = "rgba(20, 184, 166, 0.4)"
        btn_grad_start = "#0d9488"
        btn_grad_end = "#10b981"

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
    /* Block container */
    .block-container {{
        padding-top: 2rem;
        max-width: 1300px;
    }}
    /* Hero gradient */
    .hero {{
        padding: 2rem 2.2rem;
        border-radius: 18px;
        margin-bottom: 1.2rem;
        background: linear-gradient(135deg, {hero_grad_start} 0%, {hero_grad_mid} 50%, {hero_grad_end} 100%);
        color: white;
        box-shadow: 0 10px 30px rgba(13, 148, 136, 0.25);
    }}
    .hero h1 {{
        margin: 0;
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -.5px;
    }}
    .hero p {{
        margin: .4rem 0 0;
        opacity: .95;
        font-size: 1.02rem;
    }}
    /* Card stat */
    .card {{
        background: {surface_alt};
        border: 1px solid {border};
        border-radius: 14px;
        padding: 1rem 1.2rem;
        height: 100%;
    }}
    .card .label {{
        font-size: .78rem;
        text-transform: uppercase;
        letter-spacing: .08em;
        opacity: .7;
        color: {text_muted};
    }}
    .card .value {{
        font-size: 1.7rem;
        font-weight: 800;
        line-height: 1.25;
        word-break: break-all;
        color: {text};
    }}
    .card .value.small {{
        font-size: 1.15rem;
    }}
    /* Pill chip */
    .pill {{
        display: inline-block;
        padding: .15rem .65rem;
        border-radius: 999px;
        margin: 0 .3rem .3rem 0;
        background: {pill_bg};
        border: 1px solid {pill_border};
        font-size: .82rem;
        color: {text};
    }}
    /* Primary button */
    div.stButton > button[kind="primary"] {{
        background: linear-gradient(90deg, {btn_grad_start}, {btn_grad_end});
        border: 0;
        font-weight: 700;
        border-radius: 10px;
        padding: .6rem 1rem;
        color: white;
    }}
    /* Section title */
    .section-title {{
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        color: {text_muted};
        margin-bottom: 12px;
        padding-bottom: 4px;
        border-bottom: 1px solid {border};
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
    </style>
    """, unsafe_allow_html=True)


# Initialize theme state
if "theme_dark" not in st.session_state:
    st.session_state["theme_dark"] = True

apply_theme(st.session_state["theme_dark"])

# ---------------------------------------------------------------------------
# Hero section
# ---------------------------------------------------------------------------
st.markdown(
    """
<div class="hero">
  <h1>🕸️ WebRank Explorer</h1>
  <p>Masukkan sebuah link website. Aplikasi akan menelusuri tautan-tautannya, membangun graph
  keterhubungan antarwebsite, lalu menghitung <b>PageRank</b> untuk menemukan website paling berpengaruh.</p>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar: pengaturan
# ---------------------------------------------------------------------------
with st.sidebar:
    # Theme toggle di paling atas sidebar
    st.markdown("### 🎨 Tema")
    if st.session_state["theme_dark"]:
        if st.button("☀️ Light Mode", use_container_width=True):
            st.session_state["theme_dark"] = False
            st.rerun()
    else:
        if st.button("🌙 Dark Mode", use_container_width=True):
            st.session_state["theme_dark"] = True
            st.rerun()

    st.markdown("---")
    st.markdown("### ⚙️ Pengaturan Crawl")
    depth = st.slider("Kedalaman (depth)", 1, 3, 2,
                      help="Seberapa jauh tautan diikuti. Makin dalam makin lama.")
    max_pages = st.slider("Maks. total halaman", 10, 150, 50, step=10)
    per_domain = st.slider("Maks. halaman per website", 1, 15, 5)
    delay = st.slider("Jeda antar request (detik)", 0.2, 3.0, 0.5, step=0.1,
                      help="Jeda sopan terhadap website yang sama.")
    max_seconds = st.slider("Batas waktu crawl (detik)", 20, 300, 90, step=10)
    respect_robots = st.checkbox("Patuhi robots.txt", value=False,
                                 help="Default nonaktif agar bisa crawl website apapun. Aktifkan untuk crawling sopan.")
    weighted = st.checkbox("Bobot edge = jumlah tautan", value=True)
    damping = st.slider("Damping factor PageRank", 0.50, 0.99, 0.85, step=0.01)
    restrict_seed = st.checkbox("Batasi ke domain seed", value=False,
                                help="Hanya crawl domain yang sama dengan seed URL.")
    st.caption("Tips: mulai dengan pengaturan kecil agar cepat, lalu naikkan bertahap.")

    st.markdown("---")
    st.markdown("### 🗄️ Database")
    show_history = st.checkbox("Tampilkan history crawl", value=False)

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
c_in, c_btn = st.columns([5, 1], vertical_alignment="bottom")
with c_in:
    url_input = st.text_input("🔗 Link website", placeholder="https://www.wikipedia.org",
                              label_visibility="collapsed")
with c_btn:
    run = st.button("🚀 Analisis", type="primary", use_container_width=True)

st.caption("Contoh: `https://www.wikipedia.org` · `https://news.ycombinator.com` · `https://github.com` · `https://trunojoyo.ac.id`")

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
                 "dilarang `robots.txt`, bukan halaman HTML, atau alamat tidak dapat dijangkau.")
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
    st.markdown("---")
    st.markdown('<div class="section-title">History Crawl</div>', unsafe_allow_html=True)
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
    st.info("👆 Masukkan link lalu tekan **Analisis** untuk memulai.")
    st.stop()

G, pr, seed = res["G"], res["pr"], res["seed"]
metrics_df = res["metrics_df"]
crawler = res["crawler"]
ranking = sorted(pr.items(), key=lambda x: -x[1])
top_site, top_score = ranking[0]
elapsed = res["elapsed"]

# ---------------------------------------------------------------------------
# Ringkasan stat cards
# ---------------------------------------------------------------------------
def card(col, label, value, small=False):
    col.markdown(f'<div class="card"><div class="label">{label}</div>'
                 f'<div class="value {"small" if small else ""}">{value}</div></div>',
                 unsafe_allow_html=True)

m = st.columns(4)
card(m[0], "🌐 Website ditemukan", f"{G.number_of_nodes():,}")
card(m[1], "📄 Halaman di-crawl", f"{sum(res['crawled'].values()):,}")
card(m[2], "🔗 Tautan antarwebsite", f"{G.number_of_edges():,}")
card(m[3], "🏆 Paling penting", top_site, small=True)
st.write("")

# ---------------------------------------------------------------------------
# Tabs (mirip referensi, dengan emoji)
# ---------------------------------------------------------------------------
tab_graph, tab_rank, tab_rel, tab_metrics, tab_dl = st.tabs([
    "🕸️ Graph",
    "🏆 Peringkat PageRank",
    "🔗 Website Terkait",
    "📊 Metrik Graph",
    "📥 Unduh",
])

# --------------------------------------------------------------------------
# Tab 1: Graph (Flourish-style dengan D3.js)
# --------------------------------------------------------------------------
with tab_graph:
    n_total = G.number_of_nodes()
    top_n = n_total if n_total <= 10 else st.slider(
        "Jumlah website ditampilkan (berdasarkan PageRank tertinggi)",
        5, n_total, min(n_total, 40)
    )

    graph_html = render_flourish_graph(
        G=G, pr=pr, seed=seed, metrics_df=metrics_df,
        top_n=top_n, height=700, dark_mode=st.session_state["theme_dark"],
    )
    import streamlit.components.v1 as components
    components.html(graph_html, height=760, scrolling=True)

    st.caption("🟡 = website awal yang Anda masukkan · ukuran & warna node = PageRank · "
               "anak panah = arah tautan · scroll untuk zoom, seret untuk menggeser.")

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
        st.markdown("**Top 10 website**")
        st.bar_chart(df_rank.head(10).set_index("Website")["PageRank"],
                     horizontal=True, color="#0d9488")
    st.success(f"**{top_site}** adalah website dengan tingkat kepentingan tertinggi "
               f"(PageRank {top_score:.5f}), karena banyak menerima tautan dari website penting lain.")

# --------------------------------------------------------------------------
# Tab 3: Website Terkait
# --------------------------------------------------------------------------
with tab_rel:
    st.markdown(f"#### Website yang terkait dengan `{seed}`")
    out_nb = sorted(G.successors(seed), key=lambda n: -pr[n]) if seed in G else []
    in_nb = sorted(G.predecessors(seed), key=lambda n: -pr[n]) if seed in G else []

    a, b = st.columns(2)
    with a:
        st.markdown(f"**➡️ Ditautkan oleh {seed}** ({len(out_nb)})")
        if out_nb:
            st.markdown("".join(f'<span class="pill">{n}</span>' for n in out_nb[:30]),
                        unsafe_allow_html=True)
        else:
            st.caption("Tidak ada.")
    with b:
        st.markdown(f"**⬅️ Menaut ke {seed}** ({len(in_nb)})")
        if in_nb:
            st.markdown("".join(f'<span class="pill">{n}</span>' for n in in_nb[:30]),
                        unsafe_allow_html=True)
        else:
            st.caption("Tidak ditemukan pada crawl ini.")

    st.markdown("**Rincian tautan dari website awal**")
    by_dst = defaultdict(list)
    for src_url, dst_url in res["page_links"]:
        if get_domain(src_url) == seed and get_domain(dst_url) != seed:
            by_dst[get_domain(dst_url)].append((src_url, dst_url))
    if not by_dst:
        st.caption("Tidak ada tautan keluar dari website awal.")
    for dst in sorted(by_dst, key=lambda n: -pr.get(n, 0)):
        pairs = by_dst[dst]
        with st.expander(f"{dst} · {len(pairs)} tautan · PageRank {pr.get(dst, 0):.5f}"):
            for src_url, dst_url in pairs[:15]:
                title = res["titles"].get(src_url) or src_url
                st.markdown(f"- {dst_url}  \n  <small>dari: {title}</small>", unsafe_allow_html=True)
            if len(pairs) > 15:
                st.caption(f"... dan {len(pairs) - 15} tautan lainnya")

# --------------------------------------------------------------------------
# Tab 4: Metrik Graph
# --------------------------------------------------------------------------
with tab_metrics:
    summary = graph_summary(G)
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
        in_dist = pd.Series([d for _, d in G.in_degree()]).value_counts().sort_index()
        st.bar_chart(in_dist)
    with dist_c2:
        st.markdown("**Distribusi Out-degree**")
        out_dist = pd.Series([d for _, d in G.out_degree()]).value_counts().sort_index()
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

# --------------------------------------------------------------------------
# Tab 5: Unduh
# --------------------------------------------------------------------------
with tab_dl:
    df_edges = pd.DataFrame(
        [{"sumber": u, "tujuan": v, "jumlah_tautan": c} for (u, v), c in res["edges"].items()]
    ).sort_values("jumlah_tautan", ascending=False)

    st.markdown("### 📥 Download Hasil Analisis")

    d1, d2 = st.columns(2)
    with d1:
        st.download_button("⬇️ pagerank.csv",
                           df_rank.to_csv(index=False).encode("utf-8"),
                           "pagerank.csv", "text/csv", use_container_width=True)
    with d2:
        st.download_button("⬇️ edges.csv",
                           df_edges.to_csv(index=False).encode("utf-8"),
                           "edges.csv", "text/csv", use_container_width=True)

    st.markdown("---")
    st.markdown("### 📁 Export ke Format Lain")

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

    st.caption(f"⏱️ Crawl selesai dalam {elapsed:.1f} detik · seed: {res['url']}")
