# Aset ilustrasi/tekstur dari Gemini (atau generator gambar lain)

Claude hanya bisa menggambar lewat kode; untuk tekstur kertas, elemen kolase, ilustrasi, pengguna dapat memakai
Gemini (mis. lewat ekstensi Chrome). Claude **menuliskan prompt-nya**, pengguna (atau Claude via browser bila tersedia)
menjalankannya, lalu file disimpan ke `projects/<p>/assets/raw/`.

## Aturan prompt
- Satu objek per gambar, **latar hijau polos #00B140**, tanpa bayangan jatuh ke latar, tanpa teks.
- Sebutkan gaya konsisten untuk seluruh video (mis. "paper cutout collage, kraft paper texture, slightly torn edges, flat lighting").
- Rasio sesuai pemakaian (objek kolase 1:1, tekstur latar 16:9).
- Contoh: `Paper cutout of a vintage Jakarta city bus, kraft paper texture, torn edges, flat studio lighting, isolated on a solid pure green background #00B140, no shadow, no text.`
- Tekstur latar (tanpa keying): `Seamless brown kraft paper texture with subtle fibers and folds, top-down, even lighting, 16:9.`

## Proses
1. `vedit key projects/<p>/assets/raw --outdir projects/<p>/assets/cut` → PNG transparan.
   Sisa hijau di tepi? naikkan `--similarity` (0.25–0.32). Objek ikut bolong? turunkan.
2. Pakai di komposisi `Collage` (`pieces[].src = "assets/cut/xxx.png"`) atau `TitleCard` (`bgImage`).
3. `vedit gfx <p> --still --only <id>` → minta persetujuan sebelum render.
