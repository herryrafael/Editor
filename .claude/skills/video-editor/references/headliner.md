# Headliner / opening video acara bisnis (60–120 detik)

## Tujuan
Membangun energi ruangan / memperkenalkan tema dalam waktu singkat. **Musik = tulang punggung**, bukan ucapan.

## Alur khusus (menggantikan tahap 3–5 umum)
1. `vedit beats music/<lagu>` → baca BPM, `downbeats`, `sections` (perubahan energi = build-up/drop).
2. Isi tabel struktur di `script.md`: tiap bagian musik → energi → isi visual → panjang shot → teks.
   Tunjukkan ke pengguna 🔒.
3. Pilih shot dari contact sheet: utamakan gerak, wajah ekspresif, crowd, detail produk/brand. Rating ★★★ saja.
4. Bangun track `video` dengan durasi **tepat di beat**: tiap item `out − in` = selisih beat (intro: per 2 bar,
   build-up: per bar → per 2 beat, drop: per beat atau setengah beat). Shot pertama harus menarik dalam 1 detik.
5. KineticText: isi `words` dengan `at` = waktu beat/downbeat (dari beats.json) — kata kunci tagline, angka pencapaian.
   `accent: true` untuk kata puncak di drop.
6. EndCard dengan logo (PNG transparan di `assets/`) di 4–6 detik terakhir; musik harus selesai alami (pilih titik
   akhir di downbeat atau pakai `fade_out`).
7. `vedit stills --overlays` → 🔒 → `vedit render` → 🔒 → `--final`.

## Aturan
- Hindari ucapan panjang; maksimal satu soundbite 3–8 dtk (di build-up atau sebelum drop).
- Loudness −14 LUFS (sudah default template). Kalau diputar di venue, tanyakan operator: kadang minta −16 atau −18.
- Layar LED panggung sering bukan 16:9 → tanyakan resolusi persis, set di `project.json`.
- Siapkan versi 9:16 untuk sosmed bila diminta (timeline terpisah, `fit: fill`, cek still agar subjek tidak terpotong).
