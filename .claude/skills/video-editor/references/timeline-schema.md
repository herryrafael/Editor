# Skema `timeline.json`

Semua waktu boleh angka detik (`83.5`) atau string (`"1:23.5"`, `"00:01:23.500"`).
Track `video` berurutan tanpa celah — posisi tiap item = jumlah durasi item sebelumnya.
Track lain (`overlays`, `voiceover`, `music`) diposisikan bebas dengan `at`.

```json
{
  "fps": 25, "width": 1920, "height": 1080,      // opsional, default dari project.json
  "fit": "fill",                                   // fill = crop memenuhi layar, fit = letterbox/pillarbox
  "dialog_gain_db": 0,
  "duck": {"threshold": 0.02, "ratio": 8, "attack": 30, "release": 500},   // null = tanpa ducking
  "sections": [{"at": 0, "title": "Cold open"}, {"at": 42, "title": "Pembukaan"}],

  "video": [
    {"id": "co01", "clip": "day1/A001.MP4", "in": "12:03.2", "out": "12:06.0", "label": "crowd wide"},
    {"id": "sb01", "clip": "day1/A014.MP4", "in": 301.4, "out": 318.9, "speed": 1.0, "gain_db": 2},
    {"id": "br01", "clip": "day1/C0021.MP4", "in": 4, "out": 7.5, "audio": "mute", "fade_in": 0.5},
    {"id": "hp01", "clip": "hp/IMG_5344.MOV", "in": 0, "out": 3, "fit": "fit"},
    {"id": "ph01", "clip": "foto/DSC0101.jpg", "duration": 4, "zoom": 0.1},
    {"id": "blk",  "type": "color", "color": "black", "duration": 2},
    {"id": "x",    "clip": "…", "in": 0, "out": 2, "skip": true}
  ],

  "voiceover": [
    {"clip": "vo/narasi_01.wav", "in": 0.4, "out": 12.8, "at": 42.0, "speed": 1.1, "gain_db": 0},
    {"clip": "day1/A014.MP4", "in": 330.0, "out": 341.2, "at": 60.0}
  ],

  "music": [
    {"file": "music/lagu.mp3", "at": 0, "in": 0, "duration": 95, "gain_db": -16, "fade_in": 1, "fade_out": 3}
  ],

  "overlays": [
    {"gfx": "title", "at": 2.0},
    {"gfx": "lt_budi", "at": 45.5},
    {"file": "assets/logo_pojok.png", "at": 0, "duration": 30, "fade_in": 0.5, "fade_out": 0.5}
  ]
}
```
(Komentar `//` di atas hanya penjelasan — JSON asli tidak boleh berisi komentar.)

## Field item `video`
| Field | Arti |
|---|---|
| `id` | unik, dipakai `stills --items`, storyboard, EDL |
| `clip` | path relatif ke `footage/` (sama seperti di catalog) atau ke folder proyek |
| `in` / `out` | rentang sumber. Foto/warna pakai `duration` |
| `speed` | 1.1 = 10% lebih cepat; audio memakai atempo (nada tetap) |
| `audio` | `"mute"` untuk b-roll tanpa suara asli |
| `gain_db` | volume suara asli item |
| `fade_in` / `fade_out` | fade dari/ke hitam (video + audio), detik |
| `fit` | override `fill`/`fit` per item (mis. video HP vertikal di timeline 16:9 → `fit`) |
| `zoom` | khusus foto: Ken Burns, 0.1 = zoom 10% sepanjang durasi |
| `vf` / `af` | filter FFmpeg tambahan, mis. `"vf": "eq=contrast=1.05:saturation=1.1"`, `"af": "afftdn=nr=10"` |
| `label` | catatan bebas (tampil di `info`, storyboard, EDL) |
| `skip` | `true` = nonaktif tanpa menghapus |

## Overlay
`gfx` merujuk `id` di `gfx.json` → file `work/gfx/<id>.mov` (render dengan `vedit gfx`). Durasi overlay = durasi file.
`file` untuk PNG/MOV/WebM beralpha sendiri; PNG wajib `duration`. `offset` = mulai dari detik ke-N file overlay.

## Pola umum
- **Talking head + b-roll (L-cut):** taruh ucapan di `voiceover` (dengan `clip` video sumbernya), lalu track `video` berisi
  potongan talking head (audio `mute`) bergantian dengan b-roll. Suara tetap mengalir tanpa putus.
- **Hasil `tighten`:** file `work/tight/<klip>.items.json` berisi `items` yang tinggal disalin ke track `video`
  (atau `voiceover` bila sumbernya file audio).
- **Potong di beat:** ambil `beats`/`downbeats` dari `.beats.json`; durasi item = selisih dua beat (frame-exact otomatis).
