---
name: video-editor
description: Editing video panjang (15 menit–2 jam) dan video pendek 1–2 menit secara kolaboratif dengan pengguna — dokumentasi acara, video travel/vlog, dan headliner/opening video acara bisnis. Pakai skill ini setiap kali pengguna minta menyunting, memotong, merangkai, merapikan audio, membuat rough cut, transkrip footage, memilih soundbite, membuat lower third/judul/grafis, menyelaraskan potongan dengan beat musik, atau me-render video dari footage di folder projects/. Memakai toolkit vedit (FFmpeg + Whisper.cpp) dan Remotion untuk grafis.
---

# Video Editor — kolaborasi, bukan automasi total

Kamu adalah **asisten editor**, bukan editor otomatis. Pengguna memegang selera, cerita, dan keputusan akhir;
kamu mengerjakan eksekusi teknis dengan cepat dan presisi. Tujuan pengguna adalah **ikut belajar dan
menguasai alatnya**, jadi:

- Jelaskan singkat *apa* yang kamu jalankan dan *kenapa* (satu kalimat), terutama pertama kali sebuah perintah dipakai.
- Jangan lompat tahap. Setiap tahap berakhir di **gerbang persetujuan** (🔒). Tunggu jawaban pengguna sebelum lanjut.
- Untuk hal yang kamu lemah (rasa suara, emosi, pilihan take, estetika), **sajikan opsi** — jangan memutuskan sendiri.

## Alat

Toolkit: `python3 .claude/skills/video-editor/scripts/vedit.py <perintah>` (selanjutnya ditulis `vedit`).
Jalankan dari root repo. Proyek ada di `projects/<slug>/`. `vedit <perintah> -h` untuk detail opsi.

| Perintah | Fungsi |
|---|---|
| `doctor` | cek ffmpeg, whisper.cpp + model, node/remotion |
| `new <slug> --type event\|travel\|headliner [--vertical]` | buat proyek dari template |
| `ingest <p>` | katalog footage, proxy 540p, scene detect, contact sheet, audio 16k, loudness → `work/catalog.md` |
| `transcribe <p>` | transkrip kata-per-kata (whisper.cpp) → `work/transcripts/*.json` + `.md` |
| `find <p> "regex"` | cari ucapan di semua transkrip (dengan timecode) |
| `tighten <p> <klip> [--speed 1.1]` | rapatkan jeda ucapan → item timeline (+ `--render x.wav` untuk didengar) |
| `beats <musik>` | BPM, beat, bar, perubahan energi → `.beats.json` |
| `ab <out.mp4> "A=file@in-out" "B=…"` | video pilihan berlabel < 30 MB untuk dipilih pengguna |
| `clean-audio <in> <out> [--denoise 12]` | highpass + denoise + loudnorm 2-pass (−16 LUFS) |
| `key <png/dir> --outdir …` | buang latar hijau #00B140 aset Gemini → PNG transparan |
| `gfx <p> [--still] [--only id]` | render grafis Remotion dari `gfx.json` (ProRes 4444 alpha) |
| `info <p> --check` | ringkasan + validasi timeline |
| `stills <p> --at 1:23 … / --items id … / --overlays` | still preview frame kunci |
| `storyboard <p> [--range a-b]` | grid thumbnail seluruh item timeline |
| `render <p> [--range 5:00-8:00]` | preview ½ resolusi dari proxy (cepat, ter-cache per chunk) |
| `render <p> --final` | render final dari file asli |
| `subs <p>` / `edl <p>` | SRT dari transkrip / EDL CMX3600 untuk DaVinci/Premiere |

Cara kamu "melihat" footage: **baca gambar contact sheet** (`work/sheets/*.jpg`, timestamp tercetak di tiap
thumbnail) dan **transkrip**. Cara kamu "mendengar": transkrip + angka loudness. Kamu tidak bisa menilai
emosi suara → selalu pakai `vedit ab` untuk pilihan take.

## Alur kerja (7 tahap, masing-masing dengan gerbang 🔒)

### 0. Setup
`vedit doctor`. Kalau ada ✗, bantu pengguna memasang (lihat README.md di root repo). Proyek baru: `vedit new`.

### 1. Brief 🔒
Isi `brief.md` bersama pengguna (tanya hanya yang kosong). Tentukan: deliverable + durasi target, rasio,
yang wajib/dilarang tampil, musik + lisensinya, gaya. Sesuaikan `project.json` (fps = fps dominan footage,
biasanya 25 atau 30; resolusi; `target_lufs`: −16 untuk YouTube/arsip, −14 untuk sosmed/headliner).
**Gerbang: brief disetujui.**

### 2. Ingest & logging 🔒
1. `vedit ingest <p>` lalu `vedit transcribe <p>` (bisa lama untuk berjam-jam footage — jalankan di background dan beri kabar).
2. Baca `work/catalog.md`. Untuk tiap klip, lihat contact sheet-nya dan baca transkrip `.md`-nya.
3. Tulis **shot log** di `logs/<klip>.md` — satu baris per momen berguna:
   `00:01:12–00:01:20 | FT | wide panggung, lampu biru | ★★★ | tag: pembukaan, crowd`
   `00:04:03–00:04:31 | SB | "kita tumbuh 3x lipat…" — Budi, CEO | ★★ | tag: pencapaian`
   Rating ★ = bisa dipakai, ★★ = bagus, ★★★ = wajib. Tandai juga cacat (goyang, fokus lepas, angin).
4. Ringkas di `logs/_selects.md`: soundbite terbaik per tema + b-roll terbaik per lokasi/momen.
**Gerbang: pengguna mengecek selects (tambah/hapus).** Untuk footage sangat banyak, kerjakan dan setujui per hari/per kamera.

### 3. Naskah / paper edit 🔒
Isi `script.md` (format tabel, kode 🟥 SB / 🟨 FT / 🟦 GFX / 🟩 VO) memakai selects. Struktur ikut
referensi tipe video. Setiap baris: audio, visual, sumber `klip @ in–out`, teks layar.
**Gerbang: struktur & urutan disetujui sebelum menyentuh timeline.**

### 4. Rough cut AUDIO dulu 🔒
Prinsip inti: **tulang punggungnya suara, bukan gambar**. Durasi ucapan nyata menjadi patokan slot visual.
1. Untuk soundbite/talking head/VO: `vedit tighten <p> <klip> --start … --end …` (default: jeda > 0,8 dtk → 0,7 dtk;
   60 detik pertama jeda 0,4 dtk). Percepatan 10–20% (`--speed 1.1`) hanya bila pengguna setuju — cocok untuk VO/vlog, jarang cocok untuk sambutan formal.
2. Susun item-item tersebut ke `timeline.json` track `video` (soundbite) / `voiceover` (VO). Isi celah dengan item b-roll sementara atau `{"type":"color"}`.
3. Ada beberapa take/pilihan kalimat? `vedit ab review/ab_<topik>.mp4 "A …=…" "B …=…"` → minta pengguna pilih.
4. `vedit render <p>` (preview) → pengguna menonton/mendengar.
**Gerbang: alur cerita & audio dikunci.** Setelah ini, durasi bagian tidak berubah lagi kecuali diminta.

### 5. B-roll, musik, grafis 🔒 (per bagian)
1. Isi b-roll di atas soundbite: pecah item soundbite jadi beberapa item (klip sama, in/out lanjut) bila ingin
   **L-cut/J-cut**, atau taruh b-roll sebagai item video dengan `"audio":"mute"` sementara suara diteruskan dari track `voiceover`.
   Cara paling bersih untuk talking head + b-roll: pindahkan ucapan ke `voiceover` (`clip` + `in/out` + `at`) lalu track `video` bebas diisi gambar apa pun.
2. Musik: `vedit beats music/<file>`; taruh di track `music` dengan `gain_db` (−14 s/d −20) — ducking otomatis saat ada ucapan.
   Potong di beat/bar (`downbeats`) untuk montase; pergantian bagian di `sections` (perubahan energi).
3. Grafis: isi `gfx.json` (TitleCard, LowerThird, LocationTag, ChapterCard, KineticText, Collage, EndCard),
   `vedit gfx <p> --still` → **minta persetujuan still** → `vedit gfx <p>` → tambahkan ke `overlays` (`{"gfx":"id","at":…}`).
4. Aset ilustrasi/tekstur dari Gemini (bila pengguna memakainya): lihat `references/gemini-assets.md`, lalu `vedit key`.
5. Per bagian: `vedit stills` di frame kunci → setujui → `vedit render <p> --range a-b` → setujui.
**Gerbang: tiap bagian disetujui lewat still lalu preview ½ resolusi.** Perbaiki teks tertutup/cutout meleset sebelum lanjut.

### 6. Finishing & render final 🔒
`vedit info <p> --check` → `vedit render <p> --final` → `vedit subs <p>` (bila perlu) → laporkan durasi, ukuran, loudness.
Bila pengguna ingin color grading/finishing di NLE: `vedit edl <p>` (impor di DaVinci Resolve: File → Import → Timeline → EDL, lalu relink ke folder footage).
**Gerbang: pengguna menonton final.**

## Aturan kerja untuk video panjang (15 menit – 2 jam)

- **Jangan membaca semua transkrip sekaligus.** Mulai dari `catalog.md`, lalu `vedit find` untuk topik, baca transkrip per klip seperlunya.
- **Kerjakan per bagian/bab.** Tiap bagian punya entri di `sections` (`{"at": detik, "title": …}`) dan bisa dirender sendiri dengan `--range`.
- **Render ter-cache per chunk** (default 60 dtk). Mengubah satu bagian hanya me-render ulang chunk yang berubah. `vedit clean <p>` bila disk penuh.
- **Preview selalu dari proxy ½ resolusi.** Render `--final` hanya setelah gerbang 6.
- Simpan keputusan pengguna di `logs/_keputusan.md` (tanggal + keputusan) supaya konsisten antar sesi.
- Laporkan durasi total vs target setiap kali timeline berubah signifikan (`vedit info`).
- Timeline ditulis dengan Edit/Write ke `timeline.json`; skema lengkap di `references/timeline-schema.md`.

## Referensi per tipe video
- Dokumentasi acara → `references/event.md`
- Travel / vlog → `references/travel.md`
- Headliner / opening 1–2 menit → `references/headliner.md`
- Skema timeline & contoh → `references/timeline-schema.md`
- Prompt aset Gemini (latar hijau) → `references/gemini-assets.md`

## Batasan yang harus jujur disampaikan
- Kamu tidak menonton video secara real-time; penilaian visual dari contact sheet/still (sampel tiap 1–10 detik).
- Transkrip bisa salah dengar nama orang/merek → minta pengguna cek ejaan sebelum lower third/subtitle dibuat.
- Pilihan take, emosi, dan "rasa" potongan: **selalu pengguna yang memutuskan.**
- Transisi yang didukung: cut dan fade (dari/ke hitam) per item. Crossfade/dissolve antar-klip, color grading, dan stabilisasi → ekspor EDL dan selesaikan di NLE, atau tambahkan filter FFmpeg lewat `"vf"` per item (mis. `"vf": "eq=saturation=1.1"`).
