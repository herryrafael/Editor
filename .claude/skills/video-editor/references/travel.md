# Video travel / vlog (15 – 40 menit)

## Tujuan
Membawa penonton *ikut jalan*: rasa tempat, ritme perjalanan, dan perubahan dari awal ke akhir.

## Struktur default
1. **Pembuka 30–60 dtk** — natural sound terkuat + janji cerita (kenapa trip ini menarik). Tempo rapat (`tighten` opening).
2. **Judul**.
3. **Bab per hari** (ChapterCard "HARI 1") atau per lokasi. Setiap lokasi baru: establishing shot + LocationTag.
4. Di dalam bab: pola **tiba → jelajah → momen (makan/orang/kejadian) → refleksi singkat**.
5. **Penutup** — refleksi/VO + montase highlight + EndCard.

## Urutan & logging
- Default kronologis memakai `created` di catalog (HP, action cam, drone). Cek zona waktu — kamera sering salah setel jam; tanyakan ke pengguna bila urutan janggal.
- `location` (ISO 6709, dari iPhone) membantu mengelompokkan per tempat.
- Tag: `establishing`, `jalan`, `makan`, `orang`, `natsound`, `drone`, `timelapse`, `ngomong-ke-kamera`, `transport`.
- Klip bicara ke kamera: transkrip → `tighten` (vlog boleh `--speed 1.1–1.15`).

## Visual
- Footage HP vertikal di timeline 16:9 → `"fit":"fit"` atau gunakan sebagai split/blur nanti di NLE.
- Drone/landscape panjang: potong 3–6 dtk, slow ramp tidak didukung → pakai `speed` konstan (mis. 0.5 untuk slow-mo dari footage 50/60 fps).
- Foto: `zoom` 0.05–0.12 untuk Ken Burns.
- HDR (iPhone HLG) otomatis di-tonemap ke SDR untuk proxy; untuk final HDR yang presisi, selesaikan di NLE via EDL.

## Audio
- Natural sound adalah emosi travel — jangan semua b-roll di-mute; pakai `gain_db` −6 s/d −12 untuk ambience.
- Ganti musik per suasana (track `music` beberapa entri, `fade_in`/`fade_out` 1–2 dtk di batas bab).
