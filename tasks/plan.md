# OmniRetail AI Phase 1 Implementation Plan

## Overview

Phase 1 fokus pada fondasi teknis yang dibutuhkan agar proyek berjalan: dockerisasi, database PostgreSQL, ETL dasar, FastAPI backend, dan reverse proxy Nginx. Tujuan utamanya adalah membangun satu jalur end-to-end yang dapat divalidasi dengan cepat.

## Architecture Decisions

- **Contract-first API:** Mulai dari definisi endpoint dan response shape sebelum implementasi. Ini menjamin interface konsisten dan memudahkan pengujian.
- **Database-first foundation:** Buat skema database yang memetakan semua file CSV utama agar ETL memiliki target yang stabil.
- **Containerized dev environment:** Docker Compose untuk developer dan homelab agar lingkungan produksi lebih mudah direplikasi.
- **Reverse proxy minimal:** Nginx hanya sebagai proxy HTTP ke FastAPI, tanpa beban monitoring Prometheus/Grafana.
- **Security boundary:** Tangani semua input sebagai tidak tepercaya, terutama query API, dan jangan commit kredensial ke repositori.

## Dependency Graph

1. Database schema
2. ETL data model + loader
3. FastAPI backend + API contract
4. Docker Compose + Nginx reverse proxy
5. Verification + test coverage

## Phase 1 Tasks

### Task 1: Define Database Schema

**Description:** Desain relasional PostgreSQL untuk dataset e-commerce dan buat model SQLAlchemy.

**Acceptance criteria:**
- Tabel `products`, `sales_transactions`, `platform_pricing`, `expenses`, `warehouse_operations` didefinisikan.
- Primary key dan foreign key ditetapkan secara eksplisit.
- Index ditambahkan pada kolom query-heavy seperti `sku`, `order_date`, `platform`, `currency`.

**Verification:**
- `app/db.py` berhasil memanggil `Base.metadata.create_all(bind=engine)`.
- Tabel-tabel muncul di database.
- Skema cocok dengan struktur kolom dataset.

**Dependencies:** None

**Files likely touched:**
- `app/models.py`
- `app/db.py`
- `scripts/load_csv_data.py`

---

### Task 2: Implement ETL for Core Dataset

**Description:** Buat pipeline ETL yang membaca CSV, membersihkan data, menormalisasi tanggal, dan memuat ke PostgreSQL.

**Acceptance criteria:**
- Tanggal distandarkan ke format `YYYY-MM-DD`.
- SKU, numerik, dan kolom penting divalidasi.
- `Sale Report.csv` dan satu file sales (`Amazon Sale Report.csv` atau `International sale Report.csv`) berhasil dimuat.

**Verification:**
- `scripts/load_csv_data.py` berjalan tanpa exception.
- Query dari database mengembalikan data yang benar.
- Data products tersedia untuk endpoint `/products`.

**Dependencies:** Task 1

**Files likely touched:**
- `scripts/load_csv_data.py`
- `app/models.py`
- `app/db.py`

---

### Task 3: Build FastAPI Skeleton and Health Endpoints

**Description:** Implementasi API kontrak minimum untuk validasi layanan.

**Acceptance criteria:**
- Endpoint `/health` mengembalikan `{ "status": "ok" }`.
- Endpoint `/products` mengembalikan daftar produk yang valid.
- Response berbentuk JSON konsisten.

**Verification:**
- `curl http://localhost:8000/health` sukses.
- `curl http://localhost:8000/products` mengembalikan array JSON.

**Dependencies:** Task 1

**Files likely touched:**
- `app/main.py`
- `app/routers/health.py`
- `app/routers/products.py`
- `app/schemas.py`

---

### Task 4: Add Docker Compose, Nginx Proxy, and Environment Configuration

**Description:** Buat lingkungan container untuk API, database, dan reverse proxy.

**Acceptance criteria:**
- `docker compose up --build` berjalan tanpa error.
- Nginx memproxy request dari port 80 ke FastAPI pada port 8000.
- Aplikasi dapat diakses melalui `http://localhost/`.

**Verification:**
- Browser atau `curl http://localhost/health` menampilkan FastAPI response.
- `docker compose ps` menunjukkan `app`, `postgres`, dan `nginx` berjalan.

**Dependencies:** Tasks 1-3

**Files likely touched:**
- `docker-compose.yml`
- `Dockerfile`
- `nginx/nginx.conf`
- `nginx/conf.d/app.conf`

---

### Task 5: Validate Full Phase 1 Flow

**Description:** Jalankan verifikasi end-to-end untuk memastikan Phase 1 selesai.

**Acceptance criteria:**
- Docker Compose menghidupkan seluruh stack.
- ETL berhasil memuat data dasar ke database.
- FastAPI bisa membaca data yang dimuat.
- Nginx melayani request dengan benar.

**Verification:**
- `docker compose ps` menunjukkan semua service sehat.
- Response `/products` berisi data dari database.
- `docker compose logs` tidak menunjukkan error kritis.

**Dependencies:** Tasks 1-4

**Files likely touched:**
- `tasks/plan.md`
- `tasks/todo.md`
- `scripts/load_csv_data.py`
- `app/main.py`

---

## Checkpoints

### Checkpoint 1: After Task 2
- [ ] Database schema dibuat
- [ ] ETL awal berhasil
- [ ] Product data dapat divalidasi di PostgreSQL

### Checkpoint 2: After Task 4
- [ ] Docker Compose berjalan
- [ ] FastAPI dan Nginx dapat diakses
- [ ] `/health` dan `/products` sukses

### Checkpoint 3: Phase 1 Complete
- [ ] End-to-end flow terverifikasi
- [ ] Phase 2 dapat dimulai dengan confidence
