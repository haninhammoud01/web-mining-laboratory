# Web Crawler PageRank Analyzer

Aplikasi web berbasis **Web Crawling** dan **PageRank Analysis** untuk menelusuri hubungan tautan antarhalaman website, membangun *directed graph*, serta mengidentifikasi website yang memiliki tingkat pengaruh tertinggi berdasarkan struktur tautannya.

Aplikasi ini dikembangkan menggunakan **Streamlit, NetworkX, PyVis (vis.js), dan curl_cffi** dengan visualisasi graph interaktif serta fitur penyimpanan riwayat crawling menggunakan SQLite.

---

## ✨ Features

- **Multi-Level Web Crawling:** Menelusuri website menggunakan algoritma Breadth-First Search (BFS).
- **Directed Graph Construction:** Merepresentasikan hubungan antarwebsite dalam bentuk graf berarah.
- **PageRank Analysis:** Menghitung tingkat pengaruh setiap website menggunakan algoritma PageRank.
- **Interactive Graph Visualization:** Menampilkan jaringan website secara interaktif menggunakan PyVis dan vis.js.
- **Graph Metrics:** Menghitung berbagai metrik graf, termasuk density, diameter, in-degree, dan out-degree.
- **Crawl History:** Menyimpan riwayat analisis menggunakan database SQLite.
- **Data Export:** Mengekspor hasil analisis ke dalam format CSV, GraphML, dan JSON.
- **Parallel Crawling:** Mempercepat proses crawling menggunakan thread pool.
- **Robots.txt Support:** Mendukung pengaturan kepatuhan terhadap robots.txt.

---

## 🛠️ Tech Stack

| Technology | Description |
|---|---|
| Python 3.10+ | Bahasa pemrograman utama |
| Streamlit | Framework aplikasi web |
| NetworkX | Library analisis graph |
| PyVis | Visualisasi graph interaktif |
| vis.js | Rendering jaringan graph |
| curl_cffi | HTTP client dengan dukungan TLS fingerprint |
| Requests | HTTP client fallback |
| BeautifulSoup4 | Parsing dokumen HTML |
| Pandas | Manipulasi data tabular |
| NumPy | Komputasi numerik |
| SQLite | Penyimpanan riwayat crawling |

---

## 📁 Project Structure

```text
web-crawler-pagerank/
│
├── app.py              # Streamlit application (UI + module integration)
├── crawler.py          # Web crawler module (BFS, robots.txt, threading)
├── graph_builder.py    # Graph construction, PageRank, and metrics
├── database.py         # SQLite database and crawl history
├── requirements.txt    # Project dependencies
├── README.md           # Project documentation
│
└── exports/            # Exported GraphML, JSON, and CSV files
```

---

## 🚀 Getting Started

### Prerequisites

Pastikan perangkat telah memiliki:

- Python 3.10 atau versi lebih baru.
- pip (Python package manager).
- Koneksi internet untuk proses web crawling.

### Installation

**1. Clone repository**

```bash
git clone https://github.com/haninhammoud01/web-crawler-pagerank.git
```

**2. Masuk ke direktori project**

```bash
cd web-crawler-pagerank
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Jalankan aplikasi**

```bash
streamlit run app.py
```

**5. Buka aplikasi melalui browser**

```text
http://localhost:8501
```

---

## ⚙️ Crawl Configuration

Aplikasi menyediakan beberapa parameter untuk mengontrol proses crawling dan analisis PageRank.

| Parameter | Default | Description |
|---|---:|---|
| Depth | 2 | Kedalaman penelusuran menggunakan BFS dari seed URL |
| Maximum Total Pages | 50 | Jumlah maksimum halaman yang dapat di-crawl |
| Maximum Pages per Website | 5 | Batas halaman untuk setiap website |
| Request Delay | 0.5 seconds | Jeda antarrequest ke domain yang sama |
| Respect robots.txt | False | Mengatur kepatuhan terhadap aturan robots.txt |
| Damping Factor | 0.85 | Faktor probabilitas dalam algoritma PageRank |

> **Note:** Pengaturan robots.txt secara default dinonaktifkan. Pengguna tetap perlu memperhatikan kebijakan akses website, ketentuan layanan, dan pembatasan crawling yang berlaku.

---

## 🧩 Project Modules

### 1. `crawler.py`

Modul untuk melakukan proses web crawling menggunakan pendekatan class-based.

**Key Features:**

- Breadth-First Search (BFS) untuk crawling multi-level.
- Pengaturan kedalaman crawling melalui parameter `depth`.
- Thread pool untuk paralelisasi dengan default 8 workers.
- Dukungan robots.txt yang dapat diaktifkan atau dinonaktifkan.
- `curl_cffi` sebagai HTTP backend utama dengan dukungan impersonasi TLS fingerprint browser.
- Fallback menggunakan Requests dengan browser User-Agent.
- Polite delay antarrequest pada domain yang sama.
- Pembatasan waktu crawling dan jumlah halaman.
- Filter domain menggunakan opsi `restrict_to_seed_domain`.
- Dukungan berbagai TLD Indonesia seperti `.ac.id`, `.co.id`, dan `.or.id`.
- Setiap subdomain diperlakukan sebagai website terpisah.

**Example:**

```text
en.wikipedia.org != fr.wikipedia.org
```

Kedua subdomain tersebut diperlakukan sebagai node yang berbeda dalam graph.

### 2. `graph_builder.py`

Modul untuk membangun graph dan melakukan analisis PageRank menggunakan NetworkX.

**Main Functions:**

| Function | Description |
|---|---|
| `build_graph(crawler, weighted)` | Membangun Directed Graph berdasarkan hasil crawling |
| `pagerank(G, damping)` | Menghitung PageRank menggunakan NetworkX |
| `pagerank_manual(G, damping)` | Implementasi iterasi PageRank secara manual |
| `compute_metrics(G, pr)` | Menghasilkan tabel metrik untuk setiap node |
| `graph_summary(G)` | Menghitung ringkasan metrik graph |
| `top_n_pagerank(pr, n)` | Mengambil N website dengan skor PageRank tertinggi |
| `export_graph(G, pr, dir, prefix)` | Mengekspor graph ke GraphML, JSON, dan CSV |

### 3. `database.py`

Modul untuk mengelola penyimpanan riwayat crawling menggunakan SQLite.

**Database Schema:**

Database terdiri dari empat tabel utama:

| Table | Description |
|---|---|
| `crawls` | Menyimpan log sesi crawling, seed URL, parameter, dan ringkasan hasil |
| `pages` | Menyimpan halaman yang ditemukan dalam setiap sesi crawling |
| `edges` | Menyimpan hubungan tautan antarwebsite |
| `pageranks` | Menyimpan skor PageRank setiap website |

**Main Functions:**

- `init_db()` : Inisialisasi database.
- `save_crawl_result()` : Menyimpan hasil crawling.
- `list_crawls()` : Menampilkan riwayat crawling.
- `get_crawl_detail()` : Mengambil detail hasil crawling.
- `delete_crawl()` : Menghapus riwayat crawling.

### 4. `app.py`

Modul utama yang mengintegrasikan seluruh komponen aplikasi menggunakan Streamlit.

**Application Features:**

- Hero header dengan identitas aplikasi.
- Sidebar untuk konfigurasi crawling.
- Empat kartu statistik hasil analisis.
- Lima tab utama untuk eksplorasi hasil.
- Visualisasi graph interaktif menggunakan PyVis dan vis.js.
- Force-directed graph layout.
- Horizontal bar chart untuk Top 10 PageRank.
- Distribusi in-degree dan out-degree.
- Export hasil analisis ke CSV, GraphML, dan JSON.
- Penyimpanan riwayat crawling menggunakan SQLite.

---

## 📊 Application Interface

Aplikasi memiliki lima tab utama untuk menampilkan hasil analisis.

| Tab | Description |
|---|---|
| Graph | Visualisasi jaringan website secara interaktif |
| Peringkat PageRank | Tabel peringkat dan bar chart website berdasarkan skor PageRank |
| Website Terkait | Informasi hubungan dan detail tautan antarwebsite |
| Metrik Graph | Analisis density, diameter, dan distribusi derajat graph |
| Unduh | Mengunduh hasil analisis dalam format CSV, GraphML, dan JSON |

---

## 🧠 PageRank Algorithm

PageRank merupakan algoritma untuk mengukur tingkat kepentingan suatu halaman berdasarkan struktur tautan yang mengarah kepadanya.

Algoritma ini diperkenalkan oleh Larry Page dan Sergey Brin sebagai salah satu dasar sistem pemeringkatan halaman web Google.

### Mathematical Formula

Implementasi PageRank mengacu pada konsep dalam *Bing Liu, Web Data Mining, Chapter 7.3*.

```text
PR(i) = (1 - d) / N + d * Σ (PR(j) / D_out(j))
```

Untuk setiap node j yang memiliki edge menuju node i.

**Where:**

- `PR(i)` = Skor PageRank node i.
- `d` = Damping factor (default 0.85).
- `N` = Jumlah seluruh node dalam graph.
- `D_out(j)` = Out-degree dari node j.
- `PR(j)` = Skor PageRank node j.

### How It Works

Setiap node membagikan nilai PageRank-nya secara merata kepada seluruh node yang ditautkannya.

Dengan demikian, sebuah website berpotensi memperoleh skor PageRank tinggi apabila menerima banyak tautan dari website lain yang juga memiliki tingkat kepentingan tinggi.

---

## 🔄 How Web Crawling Works

Proses crawling menggunakan algoritma Breadth-First Search (BFS) untuk menelusuri halaman web secara bertahap.

**Crawling Workflow:**

```text
       Seed URL
           |
           v
      Fetch HTML
           |
           v
     Parse HTML
           |
           v
   Extract <a href>
           |
           v
    Filter Valid URLs
           |
           v
      Add to Queue
           |
           v
   Check Depth & Limits
           |
           v
     Repeat Crawling
           |
           v
    Build Directed Graph
           |
           v
     Calculate PageRank
           |
           v
    Display Analysis
```

**Process Explanation:**

1. **Seed URL:** Menentukan URL awal sebagai titik masuk crawling.
2. **Fetch:** Mengunduh konten HTML dari halaman target.
3. **Parse:** Mengekstraksi elemen HTML menggunakan BeautifulSoup.
4. **Filter:** Memvalidasi tautan berdasarkan aturan crawling.
5. **Queue:** Memasukkan URL baru ke dalam antrian BFS.
6. **Repeat:** Mengulangi proses hingga kedalaman atau batas crawling tercapai.
7. **Graph Construction:** Mengubah hubungan tautan menjadi directed graph.
8. **PageRank Calculation:** Menghitung skor kepentingan setiap node.

---

## 🕸️ Directed Graph Representation

Hubungan antarwebsite direpresentasikan menggunakan **Directed Graph (DiGraph)**.

| Component | Description |
|---|---|
| Node | Website atau subdomain |
| Edge | Tautan dari satu website menuju website lain |
| Weight | Jumlah tautan dari website A menuju website B |

Contoh sederhana:

```text
Website A ------> Website B
    |                 |
    |                 |
    v                 v
Website C <------ Website D
```

Graph berarah memungkinkan aplikasi menganalisis pola hubungan dan distribusi pengaruh antarwebsite.

---

## 📖 Theoretical Concepts

### 1. Web Crawling

Web crawling merupakan proses otomatis untuk menelusuri halaman web, mengikuti tautan dari satu halaman ke halaman lainnya, serta mengumpulkan informasi berdasarkan aturan tertentu.

### 2. Web Structure Mining

Web Structure Mining merupakan proses menganalisis struktur hubungan antarhalaman web menggunakan informasi tautan.

Dalam project ini, struktur website direpresentasikan sebagai graph berarah untuk mempelajari pola keterhubungan antarwebsite.

### 3. Prestige and PageRank

PageRank merupakan pengembangan konsep *Prestige Rank* dalam analisis struktur web.

Beberapa konsep yang berkaitan:

- **Degree Prestige:** Mengukur tingkat prestise berdasarkan jumlah tautan masuk.
- **Proximity Prestige:** Mempertimbangkan kedekatan node terhadap node lain yang memberikan pengaruh.
- **Rank Prestige:** Mempertimbangkan tingkat prestise dari node yang memberikan tautan.
- **PageRank:** Mengembangkan konsep Rank Prestige dengan damping factor dan penanganan dangling nodes.

---

## ▶️ How to Use

1. Jalankan aplikasi menggunakan Streamlit.
2. Buka `http://localhost:8501` melalui browser.
3. Masukkan URL website yang ingin dianalisis.
4. Atur parameter crawling melalui sidebar.
5. Klik tombol **Analisis**.
6. Tunggu hingga proses crawling dan perhitungan PageRank selesai.
7. Eksplorasi hasil analisis melalui lima tab yang tersedia.
8. Unduh hasil analisis sesuai format yang dibutuhkan.

---

## 💡 Demo Recommendations

Untuk demonstrasi aplikasi, gunakan konfigurasi berikut agar proses crawling relatif cepat dengan hasil yang cukup representatif.

| Parameter | Recommended Value |
|---|---:|
| Depth | 2 |
| Maximum Total Pages | 50 |
| Maximum Pages per Website | 5 |
| Request Delay | 0.5 seconds |
| Respect robots.txt | False |
| Damping Factor | 0.85 |

### Recommended Seed URLs

| Website | Description |
|---|---|
| [Wikipedia](https://www.wikipedia.org) | Ensiklopedia online dengan jaringan tautan yang luas |
| [Hacker News](https://news.ycombinator.com) | Platform diskusi teknologi dan berita |
| [GitHub](https://github.com) | Platform pengembangan perangkat lunak |
| [Universitas Trunojoyo Madura](https://trunojoyo.ac.id) | Website resmi universitas |

> **Note:** Jumlah halaman, tautan, dan hasil PageRank bergantung pada konfigurasi crawling, respons server, ketersediaan halaman, serta aturan akses website. Hasil demo bukan angka yang dijamin tetap.

---

## 📦 Export Formats

Aplikasi mendukung beberapa format ekspor untuk kebutuhan dokumentasi dan analisis lanjutan.

| Format | Description |
|---|---|
| CSV | Menyimpan data PageRank dan hubungan antarwebsite |
| GraphML | Menyimpan struktur graph untuk analisis menggunakan tools graph lainnya |
| JSON | Menyimpan data graph dalam format terstruktur |

File hasil ekspor disimpan pada direktori:

```text
exports/
```

---

## 📚 References

1. Liu, B. *Web Data Mining*, Chapter 7.3, PageRank.
2. Page, L., Brin, S., Motwani, R., & Winograd, T. (1999). *The PageRank Citation Ranking: Bringing Order to the Web*. Technical Report, Stanford InfoLab.
3. Materi Perkuliahan, *Web Structure Mining*, Bab Mendeskripsikan Graf dan Prestise.

### Official Documentation

- [NetworkX Documentation](https://networkx.org/documentation/stable/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [PyVis Documentation](https://pyvis.readthedocs.io/)
- [curl_cffi Documentation](https://curl-cffi.readthedocs.io/)
- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)

---

## 👩‍💻 Author

**HANIN**

Informatics Engineering Student  
Universitas Trunojoyo Madura

GitHub: [@haninhammoud01](https://github.com/haninhammoud01)

---

*Developed as an academic project to explore Web Crawling, Web Structure Mining, Graph Analysis, and the PageRank algorithm.*