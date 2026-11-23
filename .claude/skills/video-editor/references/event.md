# Dokumentasi acara (15 menit – 2 jam)

## Tujuan
Arsip yang enak ditonton: penonton yang tidak hadir paham **apa yang terjadi, siapa yang bicara, apa intinya**.
Versi panjang boleh mempertahankan sesi utuh; versi recap 2–4 menit mengambil momen terbaik.

## Struktur default
1. **Cold open 20–40 dtk** — 3–6 shot paling energik + 1 kutipan terkuat. Hook di 3 detik pertama.
2. **Judul** (TitleCard) di atas wide shot venue.
3. **Kedatangan / suasana** — registrasi, dekor, tamu datang (b-roll di atas musik, 30–60 dtk).
4. **Pembukaan** — MC + sambutan, dipangkas ke kalimat inti. LowerThird tiap pembicara pertama kali muncul.
5. **Sesi-sesi** — tiap sesi = satu bab (ChapterCard). Versi panjang: sesi dipotong ke poin-poin; jeda/“eee”/salah slide dibuang.
6. **Momen kunci** — penghargaan, penandatanganan, launching, foto bersama: biarkan bernapas (suara tepuk tangan asli).
7. **Penutup** — montase senyum/salam + EndCard.

## Logging
- Tag wajib: `pembukaan`, `sambutan`, `sesi-N`, `momen-kunci`, `crowd`, `detail`, `venue`, `sponsor`, `vip`.
- Cocokkan dengan rundown resmi; catat jam dari `created` metadata kamera (multi-kamera → cocokkan jam antar kamera).
- `vedit find <p> "terima kasih|selamat datang|launching"` untuk menemukan titik penting cepat.

## Audio
- Sumber suara panggung sering dari kamera (jauh, bergema). Kalau ada rekaman mixer/lavalier terpisah, taruh di `footage/audio/` dan pakai di track `voiceover` dengan `at` yang disinkronkan (cocokkan kalimat yang sama di transkrip kedua file — selisih `start` kata = offset).
- `clean-audio --denoise 10–15` untuk sambutan yang berdesis; pengguna dengarkan A/B sebelum dipakai.
- Musik: rendah (−18 s/d −22 dB) di bawah ucapan; naik di montase.

## Pacing
- Sambutan formal: **jangan** dipercepat; cukup `tighten` dengan jeda 0,7 dtk.
- B-roll 2–4 dtk per shot; montase 1–2 dtk di beat.
- Setiap 2–3 menit beri "napas" visual (b-roll + musik) agar video panjang tidak melelahkan.

## Deliverable tambahan
- Recap: timeline terpisah (`--timeline timeline_recap.json`) memakai selects ★★★.
- Teaser 9:16: proyek baru `--vertical` atau timeline dengan `"width":1080,"height":1920,"fit":"fill"`.
