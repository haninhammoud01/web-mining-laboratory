"""
crawler.py - Modul web crawler untuk ekstraksi link antar halaman web.

Berbeda dengan implementasi umum, modul ini:
- Menggunakan class-based design untuk kemudahan testing
- Mematuhi robots.txt secara default
- Mendukung filter domain (same-domain only atau all domains)
- Memiliki progress callback untuk integrasi UI
- Thread-safe dengan thread pool untuk paralelisasi
- Normalisasi URL yang robust (handle query, fragment, trailing slash)
- Polite crawling dengan delay antar request
- Timeout & max_seconds untuk safety
"""

from __future__ import annotations

import re
import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable
from urllib.parse import urlparse, urljoin, urldefrag
from urllib.robotparser import RobotFileParser
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

# curl_cffi meniru TLS fingerprint browser asli, memungkinkan crawling website
# yang memblokir bot berbasis Python requests standar (mis. Wikipedia, GitHub).
try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

# Regex untuk ekstraksi domain dasar (mis. trunojoyo.ac.id dari https://ft.trunojoyo.ac.id)
# Untuk TLD Indonesia (ac.id, co.id, or.id, go.id, sch.id, web.id, mil.id, net.id)
# kita ambil 3 level terakhir. Untuk TLD internasional, ambil 2 level.
ID_SECOND_LEVEL = {"ac", "co", "or", "go", "sch", "web", "mil", "net"}
DOMAIN_RE_GENERIC = re.compile(r"([^.]+\.[^.]+)$")
DOMAIN_RE_ID = re.compile(r"([^.]+\.[^.]+\.[^.]+)$")

# Header standar untuk menyamarkan bot sebagai browser biasa
# Pakai User-Agent browser asli (Chrome di Windows) supaya mayoritas website menerima request.
# Beberapa website (mis. Wikipedia) akan menolak User-Agent yang terlihat seperti bot.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Fallback User-Agents kalau User-Agent utama ditolak
FALLBACK_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


def normalize_url(url: str) -> str:
    """Normalisasi URL: tambah skema, hapus fragment, hapus trailing slash.

    Args:
        url: URL mentah dari user atau dari href HTML.

    Returns:
        URL ternormalisasi, atau string kosong jika tidak valid.
    """
    if not url or not isinstance(url, str):
        return ""
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    if not parsed.netloc:
        return ""
    path = parsed.path
    if path and path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{parsed.netloc}{path}{query}"


def get_domain(url: str) -> str:
    """Ambil 'website' dari URL = subdomain penuh (tanpa path, query, fragment).

    Setiap subdomain diperlakukan sebagai website terpisah. Contoh:
    - en.wikipedia.org -> en.wikipedia.org (website A)
    - fr.wikipedia.org -> fr.wikipedia.org (website B)
    - trunojoyo.ac.id -> trunojoyo.ac.id (website C)
    - ft.trunojoyo.ac.id -> ft.trunojoyo.ac.id (website D, beda dari C)

    Ini sesuai dengan konsep "website" di referensi: setiap subdomain
    punya struktur & konten sendiri, sehingga wajar diperlakukan terpisah.

    Args:
        url: URL yang sudah ternormalisasi.

    Returns:
        Subdomain penuh (tanpa port, path, atau www prefix).
    """
    parsed = urlparse(url)
    netloc = parsed.netloc.split(":")[0]
    # Strip "www." prefix supaya www.wikipedia.org == wikipedia.org
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc if netloc else ""


def is_same_domain(url: str, seed_domain: str) -> bool:
    """Cek apakah URL masih dalam domain yang sama dengan seed."""
    if not seed_domain:
        return False
    return get_domain(url) == seed_domain


# ---------------------------------------------------------------------------
# Robots.txt checker
# ---------------------------------------------------------------------------

class RobotsCache:
    """Cache robots.txt per domain untuk menghindari fetch berulang.

    Disimpan sebagai class-level cache supaya satu instance bot
    tidak perlu fetch robots.txt berkali-kali untuk domain yang sama.
    """

    _cache: dict[str, RobotFileParser] = {}
    _lock = threading.Lock()

    @classmethod
    def is_allowed(cls, url: str, user_agent: str = "*") -> bool:
        """Cek apakah URL boleh di-crawl berdasarkan robots.txt domainnya.

        Args:
            url: URL yang ingin di-crawl.
            user_agent: User agent string untuk cek rules.

        Returns:
            True jika boleh, False jika dilarang, True jika robots.txt
            tidak ada atau gagal di-fetch (asumsi permissive).
        """
        domain = get_domain(url)
        with cls._lock:
            if domain not in cls._cache:
                parser = RobotFileParser()
                robots_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt"
                try:
                    parser.set_url(robots_url)
                    parser.read()
                except Exception:
                    parser = None
                cls._cache[domain] = parser
            rp = cls._cache[domain]
        if rp is None:
            return True
        return rp.can_fetch(user_agent, url)


# ---------------------------------------------------------------------------
# Data class untuk halaman yang sudah di-crawl
# ---------------------------------------------------------------------------

@dataclass
class Page:
    """Representasi satu halaman yang sudah di-crawl.

    Attributes:
        url: URL final halaman (setelah redirect).
        title: Judul halaman dari tag <title>.
        links: Daftar URL yang ditauni halaman ini (outgoing links).
        depth: Kedalaman halaman dari seed.
        domain: Domain dasar (mis. trunojoyo.ac.id).
    """
    url: str
    title: str = ""
    links: list[str] = field(default_factory=list)
    depth: int = 0
    domain: str = ""

    @property
    def external_links(self) -> list[str]:
        """Link yang mengarah ke domain berbeda dari halaman ini."""
        return [link for link in self.links if get_domain(link) != self.domain]


# ---------------------------------------------------------------------------
# Crawler utama
# ---------------------------------------------------------------------------

class Crawler:
    """Web crawler dengan BFS, thread pool, dan callback progress.

    Args:
        max_depth: Kedalaman maksimum (0 = hanya seed, 1 = seed + tetangga, dst).
        max_pages: Total halaman maksimum yang boleh di-crawl.
        per_domain: Batas halaman per domain (untuk mencegah satu domain
            mendominasi hasil).
        delay: Jeda antar request ke domain yang sama (detik).
        workers: Jumlah thread paralel.
        respect_robots: Jika True, cek robots.txt sebelum crawl.
        max_seconds: Batas waktu total crawl (detik).
        restrict_to_seed_domain: Jika True, hanya crawl domain yang sama
            dengan seed (cocok untuk analisis internal kampus).
        progress: Callback (level, done, total, current) untuk UI.
    """

    def __init__(
        self,
        max_depth: int = 2,
        max_pages: int = 50,
        per_domain: int = 5,
        delay: float = 0.5,
        workers: int = 4,
        respect_robots: bool = True,
        max_seconds: int = 90,
        restrict_to_seed_domain: bool = False,
        progress: Callable[[int, int, int, str], None] | None = None,
    ):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.per_domain = per_domain
        self.delay = delay
        self.workers = workers
        self.respect_robots = respect_robots
        self.max_seconds = max_seconds
        self.restrict_to_seed_domain = restrict_to_seed_domain
        self.progress = progress

        # State hasil crawl
        self.pages: dict[str, Page] = {}
        self.pages_crawled: dict[str, int] = defaultdict(int)
        self.page_links: list[tuple[str, str]] = []
        self.page_titles: dict[str, str] = {}
        self.edges: dict[tuple[str, str], int] = defaultdict(int)

        # Internal state
        self._seen_urls: set[str] = set()
        self._domain_last_request: dict[str, float] = {}
        self._domain_count: dict[str, int] = defaultdict(int)
        self._start_time: float = 0.0
        self._lock = threading.Lock()
        self._stop = False

    # ----- Public API ----------------------------------------------------

    def crawl(self, seed_urls: Iterable[str]) -> None:
        """Mulai crawling dari satu atau lebih seed URL.

        Menggunakan BFS: level 0 = seed, level 1 = link dari seed, dst.
        Berhenti jika max_pages, max_depth, atau max_seconds tercapai.

        Args:
            seed_urls: Iterable URL awal yang sudah ternormalisasi.
        """
        self._start_time = time.time()
        queue: list[tuple[str, int]] = []
        for url in seed_urls:
            url = normalize_url(url)
            if url and url not in self._seen_urls:
                queue.append((url, 0))
                self._seen_urls.add(url)

        # Track seed domain untuk filter restrict_to_seed_domain
        seed_domain = get_domain(queue[0][0]) if queue else ""

        level = 0
        while queue and not self._stop:
            if time.time() - self._start_time > self.max_seconds:
                break
            if len(self.pages) >= self.max_pages:
                break

            # Batch current level
            current_batch = [item for item in queue if item[1] == level]
            if not current_batch:
                level += 1
                continue
            queue = [item for item in queue if item[1] > level]

            # Filter batch sesuai max_pages yang tersisa
            slots = self.max_pages - len(self.pages)
            current_batch = current_batch[:slots]
            total_in_level = len(current_batch)
            done_in_level = 0

            if self.progress:
                self.progress(level, done_in_level, total_in_level,
                               current_batch[0][0] if current_batch else "")

            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                futures = {
                    pool.submit(self._crawl_page, url, depth, seed_domain): (url, depth)
                    for url, depth in current_batch
                }
                for future in as_completed(futures):
                    if self._stop:
                        break
                    _, depth = futures[future]
                    page = future.result()
                    done_in_level += 1
                    if self.progress and page:
                        self.progress(
                            level, done_in_level, total_in_level, page.url
                        )
                    if page:
                        self._register_page(page, depth)
                        # Tambah link ke queue untuk level berikutnya
                        if depth < self.max_depth:
                            for link in page.links:
                                if link not in self._seen_urls:
                                    self._seen_urls.add(link)
                                    queue.append((link, depth + 1))

            level += 1

    # ----- Internal methods ----------------------------------------------

    def _crawl_page(self, url: str, depth: int, seed_domain: str) -> Page | None:
        """Fetch satu halaman dan parse link-nya.

        Mengembalikan Page object, atau None jika gagal / ditolak robots.txt /
        domain terlarang.

        Strategi fetch (universal crawler):
        1. Coba curl_cffi dengan impersonate browser (paling tinggi peluang sukses)
           - Mendukung website ketat seperti Wikipedia, GitHub, Cloudflare, dll.
        2. Fallback ke requests standar dengan User-Agent browser
        3. Fallback lagi ke User-Agent alternatif jika masih 403
        """
        if self.respect_robots and not RobotsCache.is_allowed(url):
            return None

        # Filter domain jika restrict_to_seed_domain True
        if self.restrict_to_seed_domain and not is_same_domain(url, seed_domain):
            return None

        # Cek limit per-domain
        page_domain = get_domain(url)
        with self._lock:
            if self._domain_count[page_domain] >= self.per_domain:
                return None

        # Polite delay untuk domain yang sama
        last_request = self._domain_last_request.get(page_domain, 0)
        elapsed = time.time() - last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

        # Strategi 1: curl_cffi dengan impersonate browser (paling tinggi sukses)
        if HAS_CURL_CFFI:
            try:
                response = cffi_requests.get(
                    url,
                    impersonate="chrome120",
                    timeout=15,
                    allow_redirects=True,
                )
                if response.status_code == 200:
                    content_type = response.headers.get("Content-Type", "")
                    if "text/html" in content_type or "application/xhtml" in content_type:
                        with self._lock:
                            self._domain_last_request[page_domain] = time.time()
                            self._domain_count[page_domain] += 1
                        return self._parse_html(response.text, str(response.url), depth)
            except Exception:
                pass  # lanjut ke strategi 2

        # Strategi 2: requests standar dengan User-Agent browser
        user_agents_to_try = [DEFAULT_HEADERS["User-Agent"]] + FALLBACK_USER_AGENTS

        for i, user_agent in enumerate(user_agents_to_try):
            headers = dict(DEFAULT_HEADERS)
            headers["User-Agent"] = user_agent
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=15,
                    allow_redirects=True,
                )

                # HTTP 403 = Forbidden, biasanya User-Agent ditolak. Coba UA lain.
                if response.status_code == 403 and i < len(user_agents_to_try) - 1:
                    continue

                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "")
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    return None

                with self._lock:
                    self._domain_last_request[page_domain] = time.time()
                    self._domain_count[page_domain] += 1

                return self._parse_html(response.text, response.url, depth)
            except (requests.RequestException, ConnectionError, TimeoutError):
                if i < len(user_agents_to_try) - 1:
                    continue
                return None

        return None

    def _parse_html(self, html: str, final_url: str, depth: int) -> Page:
        """Parse HTML, ekstrak judul dan semua link.

        Args:
            html: Konten HTML.
            final_url: URL final (setelah redirect).
            depth: Kedalaman halaman ini.

        Returns:
            Page object.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Ekstrak judul
        title_tag = soup.find("title")
        title = title_tag.text.strip() if title_tag else ""
        if not title:
            h1 = soup.find("h1")
            title = h1.text.strip() if h1 else final_url

        # Ekstrak semua link <a href="...">
        links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
                continue
            absolute = urljoin(final_url, href)
            normalized = normalize_url(absolute)
            if normalized and normalized != final_url:
                links.append(normalized)

        # Dedup
        links = list(dict.fromkeys(links))

        return Page(
            url=final_url,
            title=title,
            links=links,
            depth=depth,
            domain=get_domain(final_url),
        )

    def _register_page(self, page: Page, depth: int) -> None:
        """Daftarkan halaman yang sudah di-crawl ke state crawler.

        Mengisi:
        - self.pages[page.url] = Page
        - self.pages_crawled[page.domain] += 1
        - self.page_links += [(src, dst), ...]
        - self.edges[(src_domain, dst_domain)] += 1 (untuk graph antar domain)
        """
        with self._lock:
            self.pages[page.url] = page
            self.pages_crawled[page.domain] += 1
            self.page_titles[page.url] = page.title

            src_domain = page.domain
            for link in page.links:
                self.page_links.append((page.url, link))
                dst_domain = get_domain(link)
                if src_domain != dst_domain:
                    self.edges[(src_domain, dst_domain)] += 1
                # Self-loop antar halaman dalam domain yang sama tetap dicatat
                # tapi tidak masuk ke graph antar-domain

    @property
    def elapsed(self) -> float:
        """Waktu total crawling (detik)."""
        return time.time() - self._start_time

    def summary(self) -> dict:
        """Ringkasan hasil crawl untuk display."""
        return {
            "pages_crawled": len(self.pages),
            "domains_found": len(self.pages_crawled),
            "links_extracted": len(self.page_links),
            "edges_intersite": len(self.edges),
            "elapsed_seconds": round(self.elapsed, 2),
        }
