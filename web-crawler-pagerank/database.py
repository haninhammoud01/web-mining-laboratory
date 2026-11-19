"""
database.py - Modul penyimpanan history crawl ke SQLite.

Modul ini menyimpan hasil crawl ke SQLite database sehingga:
- User bisa melihat kembali hasil crawl sebelumnya tanpa re-crawl
- Hasil bisa dibandingkan antar waktu (mis. sebelum/sesudah update web)
- Tidak perlu re-crawl untuk eksplorasi ulang

Schema:
- crawls: log satu sesi crawl (timestamp, seed_url, params, summary)
- pages: halaman yang ditemukan per crawl
- edges: edge antar domain per crawl
- pageranks: skor PageRank per domain per crawl
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# Thread-local untuk handle SQLite (SQLite tidak thread-safe by default)
_local = threading.local()


def get_connection(db_path: str = "crawl_history.db") -> sqlite3.Connection:
    """Dapatkan koneksi SQLite (thread-local).

    Args:
        db_path: Path ke file .db.

    Returns:
        sqlite3.Connection instance.
    """
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(db_path, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_db(db_path: str = "crawl_history.db") -> None:
    """Buat tabel jika belum ada.

    Args:
        db_path: Path ke file .db.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS crawls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seed_url TEXT NOT NULL,
            seed_domain TEXT NOT NULL,
            started_at TEXT NOT NULL,
            elapsed_seconds REAL NOT NULL,
            max_depth INTEGER NOT NULL,
            max_pages INTEGER NOT NULL,
            per_domain INTEGER NOT NULL,
            damping REAL NOT NULL,
            num_pages INTEGER NOT NULL,
            num_domains INTEGER NOT NULL,
            num_edges INTEGER NOT NULL,
            top_domain TEXT,
            top_pagerank REAL,
            params_json TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crawl_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            domain TEXT NOT NULL,
            title TEXT,
            depth INTEGER,
            out_links_count INTEGER,
            FOREIGN KEY (crawl_id) REFERENCES crawls (id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crawl_id INTEGER NOT NULL,
            source_domain TEXT NOT NULL,
            target_domain TEXT NOT NULL,
            weight INTEGER NOT NULL,
            FOREIGN KEY (crawl_id) REFERENCES crawls (id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pageranks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crawl_id INTEGER NOT NULL,
            domain TEXT NOT NULL,
            page_rank REAL NOT NULL,
            in_degree INTEGER NOT NULL,
            out_degree INTEGER NOT NULL,
            ranking INTEGER NOT NULL,
            FOREIGN KEY (crawl_id) REFERENCES crawls (id)
        )
    """)

    # Index untuk performa query
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pages_crawl ON pages(crawl_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_crawl ON edges(crawl_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pr_crawl ON pageranks(crawl_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pr_rank ON pageranks(crawl_id, ranking)")

    conn.commit()
    conn.close()


def save_crawl_result(
    db_path: str,
    seed_url: str,
    seed_domain: str,
    elapsed: float,
    params: dict,
    num_pages: int,
    num_domains: int,
    num_edges: int,
    top_domain: str,
    top_pagerank: float,
    pages: list[dict],
    edges: list[dict],
    pageranks: list[dict],
) -> int:
    """Simpan satu sesi crawl lengkap ke database.

    Returns:
        ID crawl yang baru disimpan.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    started_at = datetime.now().isoformat(timespec="seconds")

    cur.execute("""
        INSERT INTO crawls (
            seed_url, seed_domain, started_at, elapsed_seconds,
            max_depth, max_pages, per_domain, damping,
            num_pages, num_domains, num_edges,
            top_domain, top_pagerank, params_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        seed_url,
        seed_domain,
        started_at,
        elapsed,
        params.get("max_depth", 0),
        params.get("max_pages", 0),
        params.get("per_domain", 0),
        params.get("damping", 0.85),
        num_pages,
        num_domains,
        num_edges,
        top_domain,
        top_pagerank,
        json.dumps(params),
    ))
    crawl_id = cur.lastrowid

    # Bulk insert pages
    if pages:
        cur.executemany("""
            INSERT INTO pages (crawl_id, url, domain, title, depth, out_links_count)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [(crawl_id, p["url"], p["domain"], p["title"], p["depth"], p["out_links_count"])
              for p in pages])

    if edges:
        cur.executemany("""
            INSERT INTO edges (crawl_id, source_domain, target_domain, weight)
            VALUES (?, ?, ?, ?)
        """, [(crawl_id, e["source"], e["target"], e["weight"]) for e in edges])

    if pageranks:
        cur.executemany("""
            INSERT INTO pageranks (crawl_id, domain, page_rank, in_degree, out_degree, ranking)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [(crawl_id, p["domain"], p["page_rank"], p["in_degree"],
               p["out_degree"], p["ranking"]) for p in pageranks])

    conn.commit()
    conn.close()
    return crawl_id


def list_crawls(db_path: str, limit: int = 50) -> pd.DataFrame:
    """Ambil daftar sesi crawl yang tersimpan.

    Args:
        db_path: Path ke file .db.
        limit: Maksimum jumlah baris.

    Returns:
        DataFrame dengan ringkasan crawl history.
    """
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT id, seed_url, seed_domain, started_at, elapsed_seconds, "
        "num_pages, num_domains, num_edges, top_domain, top_pagerank "
        "FROM crawls ORDER BY id DESC LIMIT ?",
        conn,
        params=(limit,),
    )
    conn.close()
    return df


def get_crawl_detail(db_path: str, crawl_id: int) -> dict:
    """Ambil detail satu crawl: metadata, top pagerank, edges.

    Args:
        db_path: Path ke file .db.
        crawl_id: ID crawl.

    Returns:
        Dict {crawl_info, top_pageranks, edges}.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM crawls WHERE id = ?", (crawl_id,))
    crawl_info = dict(cur.fetchone() or {})

    cur.execute("""
        SELECT domain, page_rank, in_degree, out_degree, ranking
        FROM pageranks WHERE crawl_id = ?
        ORDER BY ranking LIMIT 20
    """, (crawl_id,))
    top_pageranks = [dict(row) for row in cur.fetchall()]

    cur.execute("""
        SELECT source_domain, target_domain, weight
        FROM edges WHERE crawl_id = ?
        ORDER BY weight DESC LIMIT 50
    """, (crawl_id,))
    edges = [dict(row) for row in cur.fetchall()]

    conn.close()
    return {
        "crawl_info": crawl_info,
        "top_pageranks": top_pageranks,
        "edges": edges,
    }


def delete_crawl(db_path: str, crawl_id: int) -> None:
    """Hapus satu crawl dan semua data terkait."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DELETE FROM pages WHERE crawl_id = ?", (crawl_id,))
    cur.execute("DELETE FROM edges WHERE crawl_id = ?", (crawl_id,))
    cur.execute("DELETE FROM pageranks WHERE crawl_id = ?", (crawl_id,))
    cur.execute("DELETE FROM crawls WHERE id = ?", (crawl_id,))
    conn.commit()
    conn.close()
