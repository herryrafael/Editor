# Editor — editing video panjang bersama Claude Code

Skill Claude Code + toolkit untuk menyunting **dokumentasi acara**, **video travel**, dan **headliner/opening
acara bisnis** (1–2 menit sampai 2 jam). Prinsipnya **kolaborasi, bukan automasi total**: Claude mengerjakan
eksekusi teknis (transkrip, potong jeda, menyusun timeline, grafis, render), kamu memegang cerita, selera,
dan keputusan di setiap tahap.

Diadaptasi dari alur kerja "Narasi Visual": rough cut audio dulu → Whisper + FFmpeg lokal untuk potong jeda →
pilihan take lewat video A/B → still preview → render ½ resolusi → final. Ditambah hal yang dibutuhkan video
panjang: proxy, contact sheet, pencarian transkrip, render per-chunk yang ter-cache, bab, subtitle, dan ekspor EDL.

```
.claude/skills/video-editor/
  SKILL.md               ← instruksi untuk Claude (alur 7 tahap + gerbang persetujuan)
  references/            ← playbook per tipe video, skema timeline, prompt aset Gemini
  templates/             ← template proyek (event / travel / headliner)
  scripts/vedit.py       ← toolkit CLI (Python + FFmpeg + Whisper.cpp)
remotion/                ← grafis overlay (judul, lower third, lokasi, bab, kinetic text, kolase, end card)
projects/<slug>/         ← satu folder per video
```

## Setup (sekali)

1. **FFmpeg** — macOS: `brew install ffmpeg` · Ubuntu/WSL: `sudo apt install ffmpeg` · Windows: `winget install Gyan.FFmpeg`
2. **Python 3.9+** (sudah ada di macOS/Linux).
3. **Whisper.cpp** (transkrip lokal, gratis):
   - macOS: `brew install whisper-cpp` (menyediakan `whisper-cli`)
   - Linux/WSL: `git clone https://github.com/ggml-org/whisper.cpp && cd whisper.cpp && cmake -B build && cmake --build build -j --config Release` lalu tambahkan `build/bin` ke PATH (atau set `WHISPER_CPP_BIN=/path/whisper-cli`)
   - Model (bagus untuk bahasa Indonesia, ±1,6 GB):
     `mkdir -p models && curl -L -o models/ggml-large-v3-turbo.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin`
   - Alternatif tanpa whisper.cpp: `pip install faster-whisper`
4. **Node.js 18+** lalu `cd remotion && npm install` (untuk grafis).
5. Cek: `python3 .claude/skills/video-editor/scripts/vedit.py doctor`

> Remotion gratis untuk individu dan perusahaan kecil; perusahaan yang lebih besar butuh lisensi — cek remotion.dev/license.

## Mulai proyek

```bash
python3 .claude/skills/video-editor/scripts/vedit.py new rapat-tahunan --type event   # atau travel / headliner
# salin/symlink footage ke projects/rapat-tahunan/footage/  (boleh subfolder per hari/kamera)
# musik ke music/, logo & aset ke assets/
```

Lalu buka Claude Code di folder repo ini dan minta, misalnya:

> Edit dokumentasi acara di projects/rapat-tahunan. Target versi lengkap 30 menit dan recap 3 menit.

Claude akan memakai skill `video-editor` dan berhenti di tiap gerbang:

| Tahap | Yang Claude kerjakan | Yang kamu putuskan |
|---|---|---|
| 1 Brief | menanyakan yang kurang, mengisi `brief.md` | tujuan, durasi, gaya, musik |
| 2 Ingest & logging | proxy, contact sheet, transkrip, shot log, selects | tambah/hapus selects |
| 3 Paper edit | `script.md` per adegan (🟥 SB · 🟨 FT · 🟦 GFX · 🟩 VO) | struktur & urutan |
| 4 Rough cut audio | potong jeda, susun soundbite/VO, video A/B take | take & alur cerita |
| 5 B-roll, musik, grafis | timeline per bagian, beat, Remotion, still → preview ½ res | tiap bagian |
| 6 Final | render final, subtitle, EDL | tonton & setujui |

## Perintah penting

```bash
V=".claude/skills/video-editor/scripts/vedit.py"
python3 $V ingest <proyek>                    # katalog + proxy + contact sheet + audio
python3 $V transcribe <proyek>                # transkrip kata-per-kata
python3 $V find <proyek> "terima kasih"       # cari ucapan
python3 $V tighten <proyek> <klip> --speed 1.1 --render review/tight.wav
python3 $V beats projects/<p>/music/lagu.mp3
python3 $V ab review/ab_take.mp4 "A take 1=file1.wav" "B take 2=file2.wav@0:10-0:30"
python3 $V gfx <proyek> --still               # still grafis untuk disetujui
python3 $V storyboard <proyek>                # grid semua potongan
python3 $V render <proyek> --range 5:00-8:00  # preview sebagian
python3 $V render <proyek> --final
python3 $V subs <proyek> ; python3 $V edl <proyek>
```

## Perkiraan waktu (CPU 4 core)
- Ingest: proxy ±0,3–0,5× durasi footage. Transkrip large-v3-turbo: tergantung CPU/GPU (Apple Silicon jauh lebih cepat).
- Preview ½ resolusi: ±10 menit timeline ≈ 2 menit render. Edit kecil hanya me-render ulang chunk yang berubah.
- Final 1080p: jauh lebih lama (encode kualitas tinggi dari file asli) — jalankan sekali di akhir.

## Batasan
- Transisi bawaan: cut dan fade hitam. Crossfade, color grading, stabilisasi → ekspor EDL ke DaVinci/Premiere, atau filter FFmpeg per item (`"vf"`).
- Claude "melihat" lewat contact sheet/still, bukan menonton real-time; pilihan take & rasa tetap keputusanmu.
