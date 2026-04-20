# TODO: Claude Code Bridge Optimization

Berikut adalah daftar bug yang ditemukan dan rencana peningkatan fitur berdasarkan referensi dari proxy eksternal.

## 1. Bug Kritis (Priority: High)
- [x] **Missing Parameters on Truncated JSON**: Saat model Jiutian memotong JSON di tengah jalan, bridge gagal mengekstrak `file_path` dan `content`.
    - *Solusi*: Berhasil diimplementasikan menggunakan `Robust JSON Extractor`.
- [x] **Tool Streaming Desync**: Tool call yang di-stream secara live menyebabkan Claude Code menerima JSON yang tidak valid.
    - *Solusi*: Berhasil diimplementasikan menggunakan `Buffer-and-Repair`.
- [ ] **SSE Packet Fragmentation**: Parser SSE saat ini (`split("\n\n")`) bisa gagal jika paket data terpotong di level TCP.
    - *Solusi*: Gunakan buffer byte-level yang lebih tangguh.

## 2. Stabilitas Sistem (Priority: Medium)
- [x] **Windows Console Resilience**: Bridge sering crash atau log tertahan jika terminal di-minimize/background.
    - *Solusi*: Berhasil diimplementasikan menggunakan `AttachConsole`.
- [x] **Error Propagation**: Jika API tujuan (asix.id) mengembalikan 503 atau 400, bridge mengirim `event: error` secara formal.

## 3. Peningkatan Fitur (Organ Donor)
- [ ] **Enhanced Message Merging**: Perbaiki `merge_messages` agar bisa menangani campuran tipe data (teks + gambar/file) dengan lebih baik.
- [ ] **Intelligent Syntax Repair**: Tingkatkan `repair_code` agar lebih cerdas menangani blok `try-catch` dan template literal yang kompleks.
- [x] **Logging Optimization**: Pastikan log selalu menggunakan karakter aman (ASCII) dan encoding UTF-8 untuk file.

---
*Catatan: Prioritas utama adalah mengembalikan stabilitas "Buffer-and-Repair" agar audit sistem bisa berjalan tanpa error parameter hilang.*
