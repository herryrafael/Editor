#!/usr/bin/env python3
"""vedit — toolkit editing video panjang (dokumentasi acara, travel, headliner).

Satu file, hanya butuh Python 3.9+ dan FFmpeg. Whisper.cpp (atau faster-whisper)
untuk transkrip, Node + Remotion untuk grafis.

Jalankan `python3 vedit.py -h` untuk daftar perintah.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATES = SKILL_DIR / "templates"

VIDEO_EXT = {".mp4", ".mov", ".mxf", ".mts", ".m2ts", ".avi", ".mkv", ".m4v", ".3gp", ".webm"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".aif", ".aiff"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
SR = 48000  # sample rate timeline


# ---------------------------------------------------------------- util

def die(msg: str, code: int = 1):
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(code)


def info(msg: str):
    print(msg, flush=True)


def run(cmd: list, quiet: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    cmd = [str(c) for c in cmd]
    if os.environ.get("VEDIT_DEBUG"):
        print("$ " + " ".join(cmd), file=sys.stderr)
    p = subprocess.run(cmd, stdout=subprocess.PIPE if (quiet or capture) else None,
                       stderr=subprocess.PIPE if (quiet or capture) else None, text=True)
    if p.returncode != 0:
        tail = (p.stderr or "")[-3000:]
        die(f"Perintah gagal ({cmd[0]}):\n{' '.join(cmd)[:1500]}\n--- stderr ---\n{tail}")
    return p


def ffmpeg(args: list, capture: bool = False):
    return run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error", *args], capture=capture)


def ffprobe(path: Path) -> dict:
    p = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path], capture=True)
    return json.loads(p.stdout or "{}")


def parse_time(s) -> float:
    """'90', '1:30', '00:01:30.5', '1:30.250' -> detik."""
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    if not s:
        raise ValueError("waktu kosong")
    parts = s.split(":")
    total = 0.0
    for p in parts:
        total = total * 60 + float(p)
    return total


def tc(sec: float, ms: bool = True) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}" if ms else f"{h:02d}:{m:02d}:{int(s):02d}"


def tc_frames(frames: int, fps: float) -> str:
    f = int(round(fps))
    h = frames // (3600 * f)
    m = frames // (60 * f) % 60
    s = frames // f % 60
    fr = frames % f
    return f"{h:02d}:{m:02d}:{s:02d}:{fr:02d}"


def safe_name(clip_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", clip_id.replace("/", "__"))


def fps_of(stream: dict) -> float:
    for key in ("avg_frame_rate", "r_frame_rate"):
        v = stream.get(key, "0/0")
        try:
            n, d = v.split("/")
            if float(d) and float(n):
                return float(n) / float(d)
        except ValueError:
            pass
    return 0.0


def sha(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def file_sig(p: Path) -> list:
    try:
        st = p.stat()
        return [str(p), st.st_size, int(st.st_mtime)]
    except FileNotFoundError:
        return [str(p), 0, 0]


def is_fresh(out: Path, src: Path) -> bool:
    return out.exists() and out.stat().st_size > 0 and out.stat().st_mtime >= src.stat().st_mtime


def font_opt() -> str:
    f = os.environ.get("VEDIT_FONT")
    if f:
        return f"fontfile='{f}':"
    return ""


def esc_text(t: str) -> str:
    """Escape teks untuk drawtext."""
    return (t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019")
            .replace("%", "\\%").replace(",", "\\,"))


def atempo_chain(speed: float) -> str:
    """atempo hanya 0.5–2.0 per tahap; rantai untuk nilai di luar itu. Nada tidak berubah."""
    if abs(speed - 1.0) < 1e-6:
        return ""
    parts = []
    s = speed
    while s > 2.0:
        parts.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        parts.append("atempo=0.5")
        s /= 0.5
    parts.append(f"atempo={s:.6f}")
    return ",".join(parts)


# ---------------------------------------------------------------- project

class Project:
    def __init__(self, ref: str):
        p = Path(ref)
        if not (p / "project.json").exists():
            root = Path(os.environ.get("VEDIT_ROOT", Path.cwd()))
            p = root / "projects" / ref
        if not (p / "project.json").exists():
            die(f"Proyek tidak ditemukan: {ref} (cari project.json di {p})")
        self.dir = p.resolve()
        self.cfg = json.loads((p / "project.json").read_text())
        self.footage = self.dir / self.cfg.get("footage_dir", "footage")
        self.work = self.dir / "work"
        self.review = self.dir / "review"
        self.out = self.dir / "out"
        for d in (self.work, self.review, self.out):
            d.mkdir(parents=True, exist_ok=True)

    @property
    def slug(self) -> str:
        return self.cfg.get("slug", self.dir.name)

    def catalog(self) -> dict:
        f = self.work / "catalog.json"
        if not f.exists():
            die("Belum ada catalog. Jalankan dulu: vedit ingest <proyek>")
        return json.loads(f.read_text())

    def clip_path(self, clip: str) -> Path:
        for base in (self.footage, self.dir):
            p = base / clip
            if p.exists():
                return p
        p = Path(clip)
        if p.is_absolute() and p.exists():
            return p
        die(f"File sumber tidak ditemukan: {clip}")

    def proxy_path(self, clip: str) -> Path:
        return self.work / "proxy" / (safe_name(clip) + ".mp4")

    def transcript_path(self, clip: str) -> Path:
        return self.work / "transcripts" / (safe_name(clip) + ".json")


# ---------------------------------------------------------------- doctor / new

def whisper_bin():
    env = os.environ.get("WHISPER_CPP_BIN")
    if env:
        return env
    for b in ("whisper-cli", "whisper-cpp"):
        if shutil.which(b):
            return shutil.which(b)
    return None


def whisper_model(explicit: str | None = None):
    if explicit:
        return explicit
    if os.environ.get("WHISPER_MODEL"):
        return os.environ["WHISPER_MODEL"]
    root = Path(os.environ.get("VEDIT_ROOT", Path.cwd()))
    models = sorted((root / "models").glob("ggml-*.bin"))
    pref = ["large-v3-turbo", "large-v3", "medium", "small"]
    for key in pref:
        for m in models:
            if key in m.name:
                return str(m)
    return str(models[0]) if models else None


def remotion_dir() -> Path:
    root = Path(os.environ.get("VEDIT_ROOT", Path.cwd()))
    return Path(os.environ.get("VEDIT_REMOTION_DIR", root / "remotion"))


def cmd_doctor(a):
    ok = True

    def row(name, good, detail=""):
        nonlocal ok
        ok = ok and (good or name.startswith("(opsional)"))
        print(f"  {'✓' if good else '✗'} {name}  {detail}")

    print("Cek kebutuhan vedit:")
    row("ffmpeg", bool(shutil.which("ffmpeg")), shutil.which("ffmpeg") or "install: brew install ffmpeg / apt install ffmpeg")
    row("ffprobe", bool(shutil.which("ffprobe")))
    wb = whisper_bin()
    try:
        import faster_whisper  # noqa: F401
        fw = True
    except Exception:
        fw = False
    row("whisper.cpp (whisper-cli)", bool(wb) or fw, wb or ("pakai faster-whisper" if fw else "lihat README: build whisper.cpp"))
    wm = whisper_model()
    row("model whisper (ggml-*.bin)", bool(wm) or fw, wm or "taruh di ./models/ atau set WHISPER_MODEL")
    row("node", bool(shutil.which("node")), shutil.which("node") or "")
    rd = remotion_dir()
    row("(opsional) remotion node_modules", (rd / "node_modules" / "remotion").exists(), f"cd {rd} && npm install")
    print("Semua siap." if ok else "Ada yang belum terpasang (lihat ✗).")


def cmd_new(a):
    root = Path(os.environ.get("VEDIT_ROOT", Path.cwd()))
    d = root / "projects" / a.slug
    if (d / "project.json").exists():
        die(f"Proyek sudah ada: {d}")
    tdir = TEMPLATES / a.type
    if not tdir.exists():
        die(f"Tipe tidak dikenal: {a.type}")
    for sub in ("footage", "assets", "music", "work", "review", "out"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    for f in tdir.iterdir():
        txt = f.read_text().replace("{{slug}}", a.slug)
        (d / f.name).write_text(txt)
    cfg = json.loads((d / "project.json").read_text())
    if a.vertical:
        cfg["width"], cfg["height"] = cfg["height"], cfg["width"]
    (d / "project.json").write_text(json.dumps(cfg, indent=2) + "\n")
    info(f"✓ Proyek dibuat: {d}")
    info("  Taruh footage di footage/ (boleh subfolder per hari/kamera), musik di music/, logo/aset di assets/.")
    info(f"  Lalu: vedit ingest {a.slug}")


# ---------------------------------------------------------------- ingest

def probe_meta(path: Path) -> dict:
    j = ffprobe(path)
    fmt = j.get("format", {})
    tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"
              and not (s.get("disposition") or {}).get("attached_pic")), None)
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), None)
    m = {"duration": float(fmt.get("duration") or 0), "size_mb": round(int(fmt.get("size") or 0) / 1e6, 1)}
    created = (tags.get("com.apple.quicktime.creationdate") or tags.get("creation_time")
               or (v or {}).get("tags", {}).get("creation_time"))
    if created:
        m["created"] = created
    loc = tags.get("com.apple.quicktime.location.iso6709") or tags.get("location")
    if loc:
        m["location"] = loc
    timecode = tags.get("timecode") or next((s.get("tags", {}).get("timecode") for s in j.get("streams", [])
                                             if s.get("tags", {}).get("timecode")), None)
    if timecode:
        m["timecode"] = timecode
    if v:
        w, h = int(v.get("width", 0)), int(v.get("height", 0))
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(sd["rotation"])
        rot = int((v.get("tags") or {}).get("rotate", rot))
        if abs(rot) % 180 == 90:
            w, h = h, w
        m.update({"width": w, "height": h, "fps": round(fps_of(v), 3), "vcodec": v.get("codec_name")})
        if v.get("color_transfer") in ("arib-std-b67", "smpte2084"):
            m["hdr"] = v.get("color_transfer")
    m["has_audio"] = a is not None
    if a:
        m["audio"] = {"codec": a.get("codec_name"), "channels": a.get("channels"), "sr": int(a.get("sample_rate") or 0)}
    return m


def make_contact_sheets(src: Path, dur: float, out_prefix: Path, cols=6, rows=8) -> list:
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    for old in out_prefix.parent.glob(out_prefix.name + "_*.jpg"):
        old.unlink()
    interval = max(1.0, min(10.0, dur / (cols * rows)))
    vf = (f"fps=1/{interval:.3f},scale=320:-2,"
          f"drawtext={font_opt()}text='%{{pts\\:hms}}':x=6:y=h-th-6:fontsize=18:fontcolor=white:"
          f"box=1:boxcolor=black@0.6:boxborderw=4,"
          f"tile={cols}x{rows}:padding=4:margin=4")
    ffmpeg(["-i", src, "-vf", vf, "-q:v", "4", "-fps_mode", "passthrough", f"{out_prefix}_%02d.jpg"])
    return sorted(str(p) for p in out_prefix.parent.glob(out_prefix.name + "_*.jpg")), interval


def detect_scenes(src: Path, thr: float) -> list:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(src), "-an", "-vf",
                        f"scale=320:-2,select='gt(scene,{thr})',showinfo", "-f", "null", "-"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return [round(float(x), 2) for x in re.findall(r"pts_time:([\d.]+)", p.stderr)]


def loudness_profile(src: Path) -> dict:
    """Integrated loudness + persentase diam, untuk menebak apakah klip berisi ucapan."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(src), "-vn", "-af",
                        "silencedetect=n=-40dB:d=1.0,ebur128", "-f", "null", "-"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", p.stderr)
    silent = sum(float(x) for x in re.findall(r"silence_duration: ([\d.]+)", p.stderr))
    return {"lufs": float(lufs[-1]) if lufs else None, "silent_s": round(silent, 1)}


def cmd_ingest(a):
    pr = Project(a.project)
    if not pr.footage.exists():
        die(f"Folder footage tidak ada: {pr.footage}")
    cat_f = pr.work / "catalog.json"
    old = json.loads(cat_f.read_text()) if cat_f.exists() else {"clips": {}}
    clips = {}
    files = sorted(p for p in pr.footage.rglob("*") if p.is_file() and not p.name.startswith("."))
    if a.only:
        files = [f for f in files if Path(f.relative_to(pr.footage).as_posix()).match(a.only)]
    proxy_h = int(pr.cfg.get("proxy_height", 540))
    for i, f in enumerate(files, 1):
        ext = f.suffix.lower()
        kind = "video" if ext in VIDEO_EXT else "audio" if ext in AUDIO_EXT else "image" if ext in IMAGE_EXT else None
        if not kind:
            continue
        cid = f.relative_to(pr.footage).as_posix()
        sig = file_sig(f)
        prev = old.get("clips", {}).get(cid)
        if prev and prev.get("sig") == sig and not a.force:
            clips[cid] = prev
            info(f"[{i}/{len(files)}] {cid} — sudah, dilewati")
            continue
        info(f"[{i}/{len(files)}] {cid} ({kind})")
        m = {"kind": kind, "sig": sig}
        if kind != "image":
            m.update(probe_meta(f))
        else:
            j = ffprobe(f)
            v = j.get("streams", [{}])[0]
            m.update({"width": v.get("width"), "height": v.get("height")})
        sn = safe_name(cid)
        if kind == "video" and m.get("duration", 0) > 0:
            if not a.no_proxy:
                px = pr.proxy_path(cid)
                px.parent.mkdir(parents=True, exist_ok=True)
                if not is_fresh(px, f) or a.force:
                    info("    proxy …")
                    gop = max(1, int(round(m.get("fps") or 25)))
                    vf = f"scale=-2:{proxy_h}"
                    if m.get("hdr"):
                        vf = f"zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,{vf}"
                    args = ["-i", f, "-map", "0:v:0", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "26", "-g", str(gop), "-pix_fmt", "yuv420p"]
                    if m.get("has_audio"):
                        args += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "96k", "-ac", "2"]
                    ffmpeg(args + [px])
                m["proxy"] = str(px.relative_to(pr.dir))
            src_for_analysis = pr.proxy_path(cid) if pr.proxy_path(cid).exists() else f
            info("    scene detect …")
            m["scenes"] = detect_scenes(src_for_analysis, float(pr.cfg.get("scene_threshold", 0.3)))
            info("    contact sheet …")
            sheets, interval = make_contact_sheets(src_for_analysis, m["duration"], pr.work / "sheets" / sn)
            m["sheets"] = [str(Path(s).relative_to(pr.dir)) for s in sheets]
            m["sheet_interval"] = round(interval, 2)
        elif kind == "image":
            m["sheets"] = [str(f.relative_to(pr.dir))]
        if kind in ("video", "audio") and m.get("has_audio", kind == "audio"):
            m["has_audio"] = True
            wav = pr.work / "audio16k" / (sn + ".wav")
            wav.parent.mkdir(parents=True, exist_ok=True)
            if not is_fresh(wav, f) or a.force:
                ffmpeg(["-i", f, "-vn", "-map", "0:a:0", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav])
            m["wav16k"] = str(wav.relative_to(pr.dir))
            m.update(loudness_profile(wav))
        clips[cid] = m
    catalog = {"project": pr.slug, "clips": clips}
    cat_f.write_text(json.dumps(catalog, indent=1, ensure_ascii=False))
    write_catalog_md(pr, catalog)
    tot = sum(c.get("duration", 0) for c in clips.values())
    info(f"✓ {len(clips)} file, total {tc(tot, ms=False)} → {cat_f.relative_to(pr.dir)} + work/catalog.md")


def write_catalog_md(pr: Project, catalog: dict):
    lines = [f"# Katalog footage — {pr.slug}", "",
             "| # | Klip | Jenis | Durasi | Res/fps | Dibuat | Audio | Scene | Transkrip |",
             "|---|---|---|---|---|---|---|---|---|"]
    clips = catalog["clips"]
    order = sorted(clips, key=lambda k: (clips[k].get("created") or "", k))
    for n, cid in enumerate(order, 1):
        c = clips[cid]
        res = f"{c.get('width', '')}x{c.get('height', '')}" + (f"@{c['fps']:g}" if c.get("fps") else "")
        aud = ""
        if c.get("has_audio"):
            aud = f"{c.get('lufs', '?')} LUFS, diam {c.get('silent_s', '?')}s"
        tr = pr.transcript_path(cid)
        trs = ""
        if tr.exists():
            j = json.loads(tr.read_text())
            words = sum(len(s.get("words", [])) for s in j.get("segments", []))
            trs = f"{words} kata"
        lines.append(f"| {n} | `{cid}` | {c['kind']} | {tc(c.get('duration', 0), ms=False)} | {res} | "
                     f"{(c.get('created') or '')[:19]} | {aud} | {len(c.get('scenes', []))} | {trs} |")
    lines += ["", "Urutan berdasarkan waktu rekam (created). Contact sheet: work/sheets/, transkrip: work/transcripts/."]
    (pr.work / "catalog.md").write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------- transcribe

def parse_whisper_cpp_json(j: dict) -> list:
    segs = []
    for s in j.get("transcription", []):
        words, cur = [], None
        for t in s.get("tokens", []):
            txt = t.get("text", "")
            if not txt or re.match(r"^\s*\[_?[A-Z_]+.*\]\s*$", txt) or txt.startswith("[_"):
                continue
            t0 = t["offsets"]["from"] / 1000.0
            t1 = t["offsets"]["to"] / 1000.0
            if cur is None or txt.startswith(" "):
                if cur and cur["w"].strip():
                    words.append(cur)
                cur = {"w": txt.strip(), "start": t0, "end": t1, "p": t.get("p", 1.0)}
            else:
                cur["w"] += txt
                cur["end"] = t1
                cur["p"] = min(cur["p"], t.get("p", 1.0))
        if cur and cur["w"].strip():
            words.append(cur)
        for w in words:
            w["p"] = round(w["p"], 3)
            w["start"] = round(w["start"], 3)
            w["end"] = round(max(w["end"], w["start"]), 3)
        segs.append({"start": s["offsets"]["from"] / 1000.0, "end": s["offsets"]["to"] / 1000.0,
                     "text": s.get("text", "").strip(), "words": words})
    return [s for s in segs if s["text"]]


def transcribe_one(wav: Path, out_json: Path, lang: str, model: str | None, threads: int, extra: list):
    wb = whisper_bin()
    if wb:
        m = whisper_model(model)
        if not m:
            die("Model whisper.cpp tidak ditemukan. Taruh ggml-*.bin di ./models/ atau set WHISPER_MODEL.")
        base = out_json.with_suffix("")
        run([wb, "-m", m, "-f", wav, "-l", lang, "-t", threads, "-ojf", "-of", base, *extra])
        raw = Path(str(base) + ".json")
        j = json.loads(raw.read_text(errors="replace"))
        segs = parse_whisper_cpp_json(j)
        raw.unlink()
        engine = f"whisper.cpp:{Path(m).name}"
    else:
        try:
            from faster_whisper import WhisperModel
        except Exception:
            die("Tidak ada whisper.cpp (whisper-cli) maupun faster-whisper. Lihat README bagian setup.")
        size = model or os.environ.get("FASTER_WHISPER_MODEL", "large-v3-turbo")
        wm = WhisperModel(size, compute_type="int8")
        it, _ = wm.transcribe(str(wav), language=lang, word_timestamps=True, vad_filter=True)
        segs = [{"start": s.start, "end": s.end, "text": s.text.strip(),
                 "words": [{"w": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3),
                            "p": round(w.probability, 3)} for w in (s.words or [])]} for s in it]
        engine = f"faster-whisper:{size}"
    out_json.write_text(json.dumps({"engine": engine, "language": lang, "segments": segs}, ensure_ascii=False, indent=0))
    md = [f"[{tc(s['start'], ms=False)}] {s['text']}" for s in segs]
    out_json.with_suffix(".md").write_text("\n".join(md) + "\n")
    return segs


def cmd_transcribe(a):
    pr = Project(a.project)
    cat = pr.catalog()
    lang = a.lang or pr.cfg.get("language", "id")
    todo = [(cid, c) for cid, c in cat["clips"].items() if c.get("wav16k")]
    if a.only:
        todo = [(cid, c) for cid, c in todo if Path(cid).match(a.only)]
    for i, (cid, c) in enumerate(todo, 1):
        out = pr.transcript_path(cid)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists() and not a.force:
            continue
        if not a.all and c.get("lufs") is not None and c["lufs"] < -45:
            info(f"[{i}/{len(todo)}] {cid} — audio sangat pelan ({c['lufs']} LUFS), dilewati (pakai --all untuk paksa)")
            continue
        info(f"[{i}/{len(todo)}] {cid} …")
        segs = transcribe_one(pr.dir / c["wav16k"], out, lang, a.model, a.threads, a.extra or [])
        info(f"    {len(segs)} segmen")
    write_catalog_md(pr, cat)
    info("✓ Transkrip di work/transcripts/ (.json kata-per-kata, .md untuk dibaca)")


def load_words(pr: Project, clip: str) -> list:
    f = pr.transcript_path(clip)
    if not f.exists():
        die(f"Transkrip belum ada untuk {clip}. Jalankan: vedit transcribe {pr.slug}")
    j = json.loads(f.read_text())
    return [w for s in j["segments"] for w in s.get("words", [])]


def cmd_find(a):
    pr = Project(a.project)
    rx = re.compile(a.pattern, re.I)
    n = 0
    for f in sorted((pr.work / "transcripts").glob("*.json")):
        j = json.loads(f.read_text())
        cat = pr.catalog()["clips"]
        clip = next((cid for cid in cat if safe_name(cid) + ".json" == f.name), f.stem)
        for s in j["segments"]:
            if rx.search(s["text"]):
                n += 1
                print(f"{clip}  {tc(s['start'])}–{tc(s['end'])}  {s['text']}")
    info(f"— {n} hasil")


# ---------------------------------------------------------------- tighten (rapatkan jeda)

def tighten_ranges(words: list, max_gap: float, gap: float, speed: float, open_secs: float,
                   open_gap: float, open_speed: float, lo: float, hi: float, pad: float, src_dur: float,
                   t_out0: float = 0.0):
    words = [w for w in words if w["start"] >= lo and w["end"] <= hi and w["end"] > w["start"]]
    if not words:
        return []
    groups = [[words[0]["start"], words[0]["end"]]]
    for w in words[1:]:
        if w["start"] - groups[-1][1] <= max_gap:
            groups[-1][1] = max(groups[-1][1], w["end"])
        else:
            groups.append([w["start"], w["end"]])
    items, t_out, prev_out = [], t_out0, None
    for g0, g1 in groups:
        opening = t_out < open_secs
        sp = open_speed if opening else speed
        half = (open_gap if opening else gap) / 2.0
        s = max(lo, g0 - max(pad, half))
        e = min(hi, src_dur or hi, g1 + max(pad, half))
        if prev_out is not None and s < prev_out:
            s = prev_out
        if e - s < 0.05:
            continue
        items.append({"in": round(s, 3), "out": round(e, 3), "speed": round(sp, 3)})
        t_out += (e - s) / sp
        prev_out = e
    return items


def cmd_tighten(a):
    pr = Project(a.project)
    cat = pr.catalog()["clips"]
    if a.clip not in cat:
        die(f"Klip tidak ada di katalog: {a.clip}")
    c = cat[a.clip]
    words = load_words(pr, a.clip)
    lo = parse_time(a.start) if a.start else 0.0
    hi = parse_time(a.end) if a.end else c.get("duration", 1e9)
    open_speed = a.open_speed if a.open_speed else a.speed
    rngs = tighten_ranges(words, a.max_gap, a.gap, a.speed, a.open_seconds, a.open_gap, open_speed,
                          lo, hi, a.pad, c.get("duration", 0), parse_time(a.at))
    if not rngs:
        die("Tidak ada kata di rentang itu.")
    track = "voiceover" if c["kind"] == "audio" else "video"
    items, at = [], parse_time(a.at)
    for k, r in enumerate(rngs, 1):
        it = {"id": f"{a.prefix}{k:03d}", "clip": a.clip, **r}
        if track == "voiceover":
            it["at"] = round(at, 3)
            at += (r["out"] - r["in"]) / r["speed"]
        items.append(it)
    src_len = hi - lo
    new_len = sum((r["out"] - r["in"]) / r["speed"] for r in rngs)
    out = Path(a.out) if a.out else pr.work / "tight" / (safe_name(a.clip) + ".items.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"track": track, "items": items}, indent=1, ensure_ascii=False))
    info(f"✓ {len(items)} potongan, {tc(src_len)} → {tc(new_len)} ({100 * new_len / max(src_len, 1e-6):.0f}%)")
    info(f"  Item untuk track '{track}' → {out}")
    if a.render:
        dst = Path(a.render)
        render_audio_items(pr, [{"clip": a.clip, **r} for r in rngs], dst)
        info(f"  Preview audio → {dst}")


def render_audio_items(pr: Project, items: list, dst: Path):
    src = pr.clip_path(items[0]["clip"])
    parts, labels = [], []
    for k, it in enumerate(items):
        chain = f"[0:a]atrim={it['in']}:{it['out']},asetpts=PTS-STARTPTS"
        at = atempo_chain(it.get("speed", 1.0))
        if at:
            chain += "," + at
        chain += f",afade=t=in:d=0.01,areverse,afade=t=in:d=0.01,areverse[a{k}]"
        parts.append(chain)
        labels.append(f"[a{k}]")
    fc = ";".join(parts) + f";{''.join(labels)}concat=n={len(items)}:v=0:a=1[out]"
    script = dst.with_suffix(".filter.txt")
    script.write_text(fc)
    ffmpeg(["-i", src, "-filter_complex_script", script, "-map", "[out]", "-ar", str(SR), dst])
    script.unlink()


# ---------------------------------------------------------------- audio utils

def loudnorm_measure(src: Path, target: float, tp: float = -1.5, lra: float = 11) -> dict:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(src), "-vn", "-af",
                        f"loudnorm=I={target}:TP={tp}:LRA={lra}:print_format=json", "-f", "null", "-"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    if not m:
        die("Gagal mengukur loudness:\n" + p.stderr[-1500:])
    return json.loads(m.group(0))


def loudnorm_filter(meas: dict, target: float, tp: float = -1.5, lra: float = 11) -> str:
    if float(meas["input_i"]) < -70:  # hampir hening
        return "anull"
    return (f"loudnorm=I={target}:TP={tp}:LRA={lra}:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:"
            f"measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:"
            f"offset={meas['target_offset']}:linear=true")


def cmd_clean_audio(a):
    src, dst = Path(a.input), Path(a.output)
    pre = ["highpass=f=80"]
    if a.denoise:
        pre.append(f"afftdn=nr={a.denoise}")
    tmp = dst.with_name(dst.stem + ".pre.wav")
    ffmpeg(["-i", src, "-vn", "-af", ",".join(pre), "-ar", str(SR), tmp])
    meas = loudnorm_measure(tmp, a.lufs)
    ffmpeg(["-i", tmp, "-af", loudnorm_filter(meas, a.lufs), "-ar", str(SR), dst])
    tmp.unlink()
    info(f"✓ {dst}  (sebelum {meas['input_i']} LUFS → target {a.lufs})")


def cmd_key(a):
    """Buang latar hijau (#00B140) dari aset Gemini → PNG transparan."""
    srcs = []
    for s in a.inputs:
        p = Path(s)
        srcs += sorted(x for x in p.iterdir() if x.suffix.lower() in IMAGE_EXT) if p.is_dir() else [p]
    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    col = a.color.lstrip("#")
    for s in srcs:
        dst = outdir / (s.stem + ".png")
        vf = (f"format=rgba,colorkey=0x{col}:{a.similarity}:{a.blend},"
              f"despill=type=green:mix=0.5:expand=0.1,format=rgba")
        ffmpeg(["-i", s, "-vf", vf, "-frames:v", "1", "-update", "1", dst])
        info(f"✓ {dst}")


# ---------------------------------------------------------------- beats

def decode_mono(path: Path, sr: int) -> array.array:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-i", str(path), "-vn",
                        "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], stdout=subprocess.PIPE)
    if p.returncode != 0:
        die(f"Gagal decode {path}")
    a = array.array("h")
    a.frombytes(p.stdout[: len(p.stdout) // 2 * 2])
    return a


def analyze_beats(path: Path, min_bpm=70, max_bpm=180) -> dict:
    sr, hop = 11025, 256
    x = decode_mono(path, sr)
    n = len(x) // hop
    fr = sr / hop
    # energi per hop → log → onset (beda positif)
    energy = []
    for i in range(n):
        seg = x[i * hop:(i + 1) * hop]
        energy.append(math.log1p(sum(v * v for v in seg[::2]) / (len(seg) / 2 + 1e-9)))
    onset = [0.0] + [max(0.0, energy[i] - energy[i - 1]) for i in range(1, n)]
    # buang tren lokal
    w = int(fr * 0.5)
    pre = [0.0]
    for v in onset:
        pre.append(pre[-1] + v)
    on = []
    for i in range(n):
        lo_, hi_ = max(0, i - w), min(n, i + w)
        on.append(max(0.0, onset[i] - (pre[hi_] - pre[lo_]) / (hi_ - lo_)))
    # tempo: autokorelasi
    lag_lo, lag_hi = int(fr * 60 / max_bpm), int(fr * 60 / min_bpm) + 1
    def ac(lag):
        return sum(on[i] * on[i - lag] for i in range(lag, n))
    best_lag, best = lag_lo, -1.0
    for lag in range(lag_lo, lag_hi):
        bpm = 60 * fr / lag
        s = ac(lag) * math.exp(-0.5 * (math.log2(bpm / 120)) ** 2)  # bias ringan ke ~120 BPM
        if s > best:
            best, best_lag = s, lag
    # interpolasi parabola → periode pecahan (resolusi hop terlalu kasar untuk BPM presisi)
    y0, y1, y2 = ac(best_lag - 1), ac(best_lag), ac(best_lag + 1)
    den = y0 - 2 * y1 + y2
    period = best_lag + (0.5 * (y0 - y2) / den if den else 0.0)
    ip = int(round(period))
    # fase: pilih offset dengan jumlah onset terbesar
    best_phase, bs = 0, -1.0
    span = min(n, int(fr * 12))  # fase dari ~12 detik pertama, supaya tidak rusak oleh drift periode
    for ph in range(ip):
        s = sum(on[int(round(ph + m * period))] for m in range(int((span - ph) / period)))
        if s > bs:
            bs, best_phase = s, ph
    # beat tracking: prediksi pakai periode pecahan, snap ke puncak onset terdekat (±10%)
    beats, pos = [], float(best_phase)
    tol = max(1, int(period * 0.2))
    thr = sorted(on)[int(len(on) * 0.9)] if on else 0
    while pos < n:
        i = min(n - 1, int(round(pos)))
        lo_, hi_ = max(0, i - tol), min(n, i + tol + 1)
        j = max(range(lo_, hi_), key=lambda k: on[k])
        if on[j] < thr:  # tidak ada onset jelas → pakai prediksi
            j = i
        beats.append(j)
        pos = j + period
    beat_t = [round(b / fr, 3) for b in beats]
    if len(beat_t) > 2:
        period = (beats[-1] - beats[0]) / (len(beats) - 1)
    # downbeat: fase 0..3 dengan energi beat tertinggi
    phase = max(range(4), key=lambda p: sum(energy[b] for b in beats[p::4]))
    downbeats = beat_t[phase::4]
    # section: rata2 energi per bar, tandai lompatan
    bars = []
    for k in range(phase, len(beats) - 4, 4):
        seg = energy[beats[k]:beats[k + 4]]
        bars.append((beat_t[k], sum(seg) / max(1, len(seg))))
    sections = []
    for k in range(1, len(bars)):
        prev = sum(b[1] for b in bars[max(0, k - 2):k]) / min(2, k)
        if abs(bars[k][1] - prev) > 0.6:
            sections.append({"at": bars[k][0], "change": "naik" if bars[k][1] > prev else "turun"})
    hits = sorted(range(n), key=lambda k: on[k], reverse=True)[: max(8, len(beats) // 8)]
    hits = sorted(round(h / fr, 3) for h in hits)
    return {"file": str(path), "duration": round(len(x) / sr, 3), "bpm": round(60 * fr / period, 1),
            "beats": beat_t, "downbeats": downbeats, "sections": sections, "hits": hits}


def cmd_beats(a):
    res = analyze_beats(Path(a.input), a.min_bpm, a.max_bpm)
    out = Path(a.out) if a.out else Path(a.input).with_suffix(".beats.json")
    out.write_text(json.dumps(res, indent=1))
    info(f"✓ {res['bpm']} BPM, {len(res['beats'])} beat, {len(res['downbeats'])} bar, "
         f"{len(res['sections'])} perubahan energi → {out}")
    for s in res["sections"][:20]:
        info(f"   {tc(s['at'])}  energi {s['change']}")


# ---------------------------------------------------------------- A/B review

def cmd_ab(a):
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    W, H, fps = 640, 360, 25
    parts = []
    tmpdir = out.parent / (out.stem + "_tmp")
    tmpdir.mkdir(exist_ok=True)
    for k, spec in enumerate(a.options):
        if "=" not in spec:
            die(f"Format opsi: 'LABEL=path[@mulai-selesai]' — dapat: {spec}")
        label, rest = spec.split("=", 1)
        rng = None
        if "@" in rest:
            rest, r = rest.rsplit("@", 1)
            s, e = r.split("-")
            rng = (parse_time(s), parse_time(e))
        src = Path(rest)
        m = probe_meta(src)
        ss = ["-ss", str(rng[0]), "-t", str(rng[1] - rng[0])] if rng else []
        dur = (rng[1] - rng[0]) if rng else m["duration"]
        title = esc_text(label)
        sub = esc_text(src.name + (f"  {tc(rng[0])}–{tc(rng[1])}" if rng else ""))
        dt = (f"drawtext={font_opt()}text='{title}':fontsize=44:fontcolor=white:x=24:y=20:box=1:boxcolor=black@0.6:boxborderw=10,"
              f"drawtext={font_opt()}text='{sub}':fontsize=18:fontcolor=white@0.85:x=24:y=h-th-20")
        part = tmpdir / f"p{k}.mp4"
        if m.get("width"):
            vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:-1:-1,setsar=1,fps={fps},{dt}"
            inputs = [*ss, "-i", src]
            vmap = ["-vf", vf]
        else:
            inputs = ["-f", "lavfi", "-i", f"color=c=0x1d2433:s={W}x{H}:r={fps}:d={dur:.3f}", *ss, "-i", src]
            vmap = ["-filter_complex", f"[0:v]{dt}[v]", "-map", "[v]", "-map", "1:a"]
        af = "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000"
        ffmpeg([*inputs, *vmap, "-af", af, "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(a.crf),
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-ar", "48000", "-ac", "2", part])
        parts.append(part)
    lst = tmpdir / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    ffmpeg(["-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", out])
    shutil.rmtree(tmpdir)
    mb = out.stat().st_size / 1e6
    info(f"✓ {out}  ({mb:.1f} MB){'  ⚠ > 30 MB, naikkan --crf' if mb > 30 else ''}")


# ---------------------------------------------------------------- timeline

class TL:
    """Timeline ter-normalisasi: semua posisi dalam frame."""

    def __init__(self, pr: Project, data: dict):
        self.pr = pr
        self.data = data
        self.fps = float(data.get("fps") or pr.cfg.get("fps", 25))
        self.W = int(data.get("width") or pr.cfg.get("width", 1920))
        self.H = int(data.get("height") or pr.cfg.get("height", 1080))
        self.fit = data.get("fit", pr.cfg.get("fit", "fill"))
        self.cat = pr.catalog()["clips"] if (pr.work / "catalog.json").exists() else {}
        self.video = []
        pos, acc = 0, 0.0  # acc = waktu eksak kumulatif → pembulatan frame tidak menumpuk (penting untuk cut di beat)
        for k, it in enumerate(data.get("video", [])):
            it = dict(it)
            it.setdefault("id", f"v{k + 1:03d}")
            if it.get("skip"):
                continue
            if it.get("type") == "color" or "clip" not in it:
                dur = parse_time(it.get("duration", 1))
                it["type"] = "color"
            else:
                it["in"] = parse_time(it.get("in", 0))
                c = self.cat.get(it["clip"], {})
                kind = c.get("kind") or ("image" if Path(it["clip"]).suffix.lower() in IMAGE_EXT else "video")
                it["type"] = kind
                if kind == "image":
                    dur = parse_time(it.get("duration", 4))
                    it["out"] = it["in"] + dur
                else:
                    it["out"] = parse_time(it["out"]) if "out" in it else it["in"] + parse_time(it.get("duration", 0))
                    if it["out"] <= it["in"]:
                        die(f"Item {it['id']}: out harus > in")
                    dur = (it["out"] - it["in"]) / float(it.get("speed", 1.0))
            acc += dur
            n = max(1, int(round(acc * self.fps)) - pos)
            it["frames"], it["start"] = n, pos
            pos += n
            self.video.append(it)
        self.frames = pos
        self.duration = pos / self.fps
        self.overlays = [dict(o) for o in data.get("overlays", []) if not o.get("skip")]
        self.voiceover = [dict(o) for o in data.get("voiceover", []) if not o.get("skip")]
        self.music = [dict(o) for o in data.get("music", []) if not o.get("skip")]
        for o in self.overlays + self.voiceover + self.music:
            o["at"] = parse_time(o.get("at", 0))
            for key in ("in", "out", "duration"):
                if key in o and o[key] is not None:
                    o[key] = parse_time(o[key])

    # -- sumber
    def src(self, it: dict, preview: bool) -> Path:
        if preview and it["type"] == "video":
            px = self.pr.proxy_path(it["clip"])
            if px.exists():
                return px
        return self.pr.clip_path(it["clip"])

    def has_audio(self, it: dict) -> bool:
        if it["type"] != "video" or it.get("audio") == "mute":
            return False
        c = self.cat.get(it["clip"])
        return c.get("has_audio", True) if c else True

    def overlay_file(self, o: dict) -> Path:
        if "gfx" in o:
            return self.pr.work / "gfx" / f"{o['gfx']}.mov"
        p = self.pr.dir / o["file"]
        return p if p.exists() else Path(o["file"])

    def overlay_len(self, o: dict) -> float:
        if o.get("duration"):
            return o["duration"]
        f = self.overlay_file(o)
        if f.suffix.lower() in IMAGE_EXT:
            return 4.0
        if not f.exists():
            die(f"Overlay belum ada: {f} (render dulu: vedit gfx {self.pr.slug})")
        return probe_meta(f)["duration"]

    def at_time(self, t: float):
        f = int(t * self.fps)
        for it in self.video:
            if it["start"] <= f < it["start"] + it["frames"]:
                return it
        return self.video[-1] if self.video else None


def load_timeline(pr: Project, path: str | None) -> TL:
    f = Path(path) if path else pr.dir / "timeline.json"
    if not f.exists():
        die(f"Timeline tidak ada: {f}")
    try:
        data = json.loads(f.read_text())
    except json.JSONDecodeError as e:
        die(f"timeline.json tidak valid: {e}")
    return TL(pr, data)


def sub_timeline(tl: TL, t0: float, t1: float) -> TL:
    """Potong timeline ke rentang [t0, t1) untuk preview per bagian."""
    d = json.loads(json.dumps(tl.data))
    f0, f1 = int(round(t0 * tl.fps)), int(round(t1 * tl.fps))
    vids = []
    for it in tl.video:
        s, e = it["start"], it["start"] + it["frames"]
        if e <= f0 or s >= f1:
            continue
        n = {k: v for k, v in it.items() if k not in ("frames", "start", "type")}
        sp = float(it.get("speed", 1.0))
        cut0 = max(0, f0 - s) / tl.fps
        cut1 = max(0, e - f1) / tl.fps
        if it["type"] == "color" or it["type"] == "image":
            n["duration"] = (it["frames"] / tl.fps) - cut0 - cut1
            if it["type"] == "image":
                n["zoom_from"] = cut0 / (it["frames"] / tl.fps)
        else:
            n["in"] = it["in"] + cut0 * sp
            n["out"] = it["out"] - cut1 * sp
        if cut0:
            n.pop("fade_in", None)
        if cut1:
            n.pop("fade_out", None)
        vids.append(n)
    d["video"] = vids
    for key in ("overlays", "voiceover", "music"):
        lst = []
        for o in d.get(key, []):
            if o.get("skip"):
                continue
            at = parse_time(o.get("at", 0)) - t0
            if at < 0:
                if key == "overlays":
                    o["offset"] = parse_time(o.get("offset", 0)) - at
                else:
                    o["in"] = parse_time(o.get("in", 0)) - at * float(o.get("speed", 1.0))
                    o.pop("fade_in", None)
                at = 0
            if at >= t1 - t0:
                continue
            o["at"] = at
            lst.append(o)
        d[key] = lst
    return TL(tl.pr, d)


# ---------------------------------------------------------------- render

def video_chain(tl: TL, it: dict, idx: int, W: int, H: int, preview: bool) -> str:
    fps, n = tl.fps, it["frames"]
    fit = it.get("fit", tl.fit)
    if fit == "fit":
        geo = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:-1:-1:color=black"
    else:
        geo = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    if it["type"] == "color":
        col = it.get("color", "black")
        ch = f"color=c={col}:s={W}x{H}:r={fps}:d={n / fps + 0.1:.3f}"
    elif it["type"] == "image":
        z = float(it.get("zoom", 0.0))
        z0 = float(it.get("zoom_from", 0.0))
        # zoompan dari 1 frame → N frame (Ken Burns halus kalau zoom > 0)
        ch = (f"[{idx}:v]{geo},scale={W * 2}:{H * 2},"
              f"zoompan=z='1+{z:.4f}*({z0:.4f}+(1-{z0:.4f})*on/{n})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":d={n}:s={W}x{H}:fps={fps}")
    else:
        sp = float(it.get("speed", 1.0))
        ch = f"[{idx}:v]setpts=(PTS-STARTPTS)/{sp:.6f},fps={fps},{geo}"
        if it.get("vf"):
            ch += "," + it["vf"]
    ch += f",setsar=1,format=yuv420p,tpad=stop_mode=clone:stop_duration=2,trim=end_frame={n},setpts=PTS-STARTPTS"
    fi, fo = float(it.get("fade_in", 0)), float(it.get("fade_out", 0))
    if fi:
        ch += f",fade=t=in:st=0:d={fi}"
    if fo:
        ch += f",fade=t=out:st={max(0.0, n / fps - fo):.3f}:d={fo}"
    return ch


def item_samples(tl: TL, it: dict) -> int:
    return int(round((it["start"] + it["frames"]) / tl.fps * SR)) - int(round(it["start"] / tl.fps * SR))


def audio_chain(tl: TL, it: dict, idx: int) -> str:
    ns = item_samples(tl, it)
    if not tl.has_audio(it):
        return f"anullsrc=r={SR}:cl=stereo,atrim=end_sample={ns}"
    sp = float(it.get("speed", 1.0))
    ch = f"[{idx}:a]asetpts=PTS-STARTPTS"
    at = atempo_chain(sp)
    if at:
        ch += "," + at
    ch += f",aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo"
    if it.get("gain_db"):
        ch += f",volume={float(it['gain_db'])}dB"
    if it.get("af"):
        ch += "," + it["af"]
    fi = max(0.01, float(it.get("fade_in", 0) or it.get("afade_in", 0)))
    fo = max(0.01, float(it.get("fade_out", 0) or it.get("afade_out", 0)))
    ch += (f",apad,atrim=end_sample={ns},afade=t=in:d={fi},"
           f"afade=t=out:st={max(0.0, ns / SR - fo):.4f}:d={fo}")
    return ch


def render_chunk(tl: TL, items: list, preview: bool, vout: Path, aout: Path, W: int, H: int, enc: list):
    inputs, chains, labels = [], [], []
    for k, it in enumerate(items):
        if it["type"] == "video":
            sp = float(it.get("speed", 1.0))
            need = it["frames"] / tl.fps * sp + 1.0
            inputs += ["-ss", f"{it['in']:.3f}", "-t", f"{need:.3f}", "-i", tl.src(it, preview)]
        elif it["type"] == "image":
            inputs += ["-i", tl.src(it, preview)]
        else:
            inputs += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]  # placeholder agar indeks konsisten
        chains.append(video_chain(tl, it, k, W, H, preview) + f"[v{k}]")
        chains.append(audio_chain(tl, it, k) + f"[a{k}]")
        labels.append(f"[v{k}][a{k}]")
    chains.append(f"{''.join(labels)}concat=n={len(items)}:v=1:a=1[vc][ac]")
    # overlay yang bersinggungan dengan chunk ini
    c0 = items[0]["start"] / tl.fps
    c1 = (items[-1]["start"] + items[-1]["frames"]) / tl.fps
    cur, k = "vc", len(items)
    for o in tl.overlays:
        o_len = tl.overlay_len(o)
        o0, o1 = o["at"], o["at"] + o_len - float(o.get("offset", 0))
        if o1 <= c0 or o0 >= c1:
            continue
        f = tl.overlay_file(o)
        if not f.exists():
            die(f"Overlay belum ada: {f}")
        skip = max(0.0, c0 - o0) + float(o.get("offset", 0))
        delay = max(0.0, o0 - c0)
        if f.suffix.lower() in IMAGE_EXT:
            inputs += ["-loop", "1", "-framerate", str(tl.fps), "-t", f"{o_len - skip + 0.1:.3f}", "-i", f]
        else:
            inputs += ["-ss", f"{skip:.3f}", "-i", f]
        oc = f"[{k}:v]fps={tl.fps},scale={W}:{H},format=yuva420p"
        fo, fi = float(o.get("fade_out", 0)), float(o.get("fade_in", 0))
        if fi and skip == 0:
            oc += f",fade=t=in:st=0:d={fi}:alpha=1"
        if fo:
            oc += f",fade=t=out:st={max(0, o_len - skip - fo):.3f}:d={fo}:alpha=1"
        oc += f",setpts=PTS-STARTPTS+{delay:.4f}/TB[o{k}]"
        chains.append(oc)
        chains.append(f"[{cur}][o{k}]overlay=eof_action=pass:format=auto,format=yuv420p[x{k}]")
        cur = f"x{k}"
        k += 1
    script = vout.with_suffix(".filter.txt")
    script.write_text(";\n".join(chains))
    ffmpeg([*inputs, "-filter_complex_script", script,
            "-map", f"[{cur}]", *enc, "-r", str(tl.fps), "-an", vout,
            "-map", "[ac]", "-c:a", "pcm_s16le", "-ar", str(SR), aout])
    script.unlink()


def item_key(it: dict) -> dict:
    """Isi item tanpa posisi — supaya chunk yang isinya sama tetap ter-cache walau bergeser."""
    return {k: v for k, v in it.items() if k not in ("start", "label")}


def split_chunks(tl: TL, target_s: float) -> list:
    """Batas chunk ditentukan oleh isi item (content-defined), bukan posisi kumulatif.
    Mengubah satu item hanya membatalkan cache chunk tempat item itu berada."""
    if not tl.video:
        return []
    lo, hi = int(target_s * 0.5 * tl.fps), int(target_s * 2 * tl.fps)
    avg = max(1, tl.frames / len(tl.video))
    m = max(1, int(round(target_s * 0.5 * tl.fps / avg)))
    chunks, cur, acc = [], [], 0
    for it in tl.video:
        cur.append(it)
        acc += it["frames"]
        h = int(sha(item_key(it)), 16)
        if acc >= hi or (acc >= lo and h % m == 0):
            chunks.append(cur)
            cur, acc = [], 0
    if cur:
        chunks.append(cur)
    return chunks


def mix_audio(tl: TL, dialog: Path, out: Path, preview: bool):
    T = tl.duration
    inputs = ["-i", dialog]
    chains = [f"[0:a]aformat=sample_fmts=fltp:channel_layouts=stereo,volume={float(tl.data.get('dialog_gain_db', 0))}dB[dlg]"]
    speech = ["[dlg]"]
    k = 1
    for o in tl.voiceover:
        src = tl.pr.clip_path(o["clip"] if "clip" in o else o["file"])
        inputs += ["-i", src]
        sp = float(o.get("speed", 1.0))
        ch = f"[{k}:a]atrim={o.get('in', 0)}" + (f":{o['out']}" if o.get("out") else "") + ",asetpts=PTS-STARTPTS"
        at = atempo_chain(sp)
        if at:
            ch += "," + at
        ch += f",aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo"
        if o.get("gain_db"):
            ch += f",volume={o['gain_db']}dB"
        ch += f",afade=t=in:d=0.01,adelay={int(o['at'] * 1000)}:all=1[vo{k}]"
        chains.append(ch)
        speech.append(f"[vo{k}]")
        k += 1
    chains.append(f"{''.join(speech)}amix=inputs={len(speech)}:normalize=0:duration=longest,apad,atrim=0:{T:.4f},asplit=2[sp][key]")
    mus = []
    for o in tl.music:
        src = tl.pr.dir / o["file"] if (tl.pr.dir / o["file"]).exists() else Path(o["file"])
        inputs += ["-i", src]
        ln = o.get("duration") or (o.get("out") - o.get("in", 0) if o.get("out") else None)
        ch = f"[{k}:a]atrim={o.get('in', 0)}" + (f":{o.get('in', 0) + ln}" if ln else "") + ",asetpts=PTS-STARTPTS"
        ch += f",aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo,volume={float(o.get('gain_db', -14))}dB"
        if o.get("fade_in"):
            ch += f",afade=t=in:d={o['fade_in']}"
        if o.get("fade_out"):
            real = ln or (probe_meta(src)["duration"] - o.get("in", 0))
            real = min(real, T - o["at"])
            ch += f",afade=t=out:st={max(0, real - float(o['fade_out'])):.3f}:d={o['fade_out']}"
        ch += f",adelay={int(o['at'] * 1000)}:all=1[m{k}]"
        chains.append(ch)
        mus.append(f"[m{k}]")
        k += 1
    if mus:
        chains.append(f"{''.join(mus)}amix=inputs={len(mus)}:normalize=0:duration=longest,apad,atrim=0:{T:.4f}[mus]")
        duck = tl.data.get("duck", {"threshold": 0.02, "ratio": 8, "attack": 30, "release": 500})
        if duck:
            chains.append(f"[mus][key]sidechaincompress=threshold={duck['threshold']}:ratio={duck['ratio']}:"
                          f"attack={duck['attack']}:release={duck['release']}[musd]")
        else:
            chains.append("[key]anullsink;[mus]anull[musd]")
        chains.append("[sp][musd]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.97:level=false[out]")
    else:
        chains.append("[key]anullsink;[sp]alimiter=limit=0.97:level=false[out]")
    script = out.with_suffix(".filter.txt")
    script.write_text(";\n".join(chains))
    ffmpeg([*inputs, "-filter_complex_script", script, "-map", "[out]", "-c:a", "pcm_s16le", "-ar", str(SR), out])
    script.unlink()


def do_render(pr: Project, tl: TL, preview: bool, out: Path, label: str):
    if not tl.video:
        die("Timeline kosong (track 'video' belum ada isinya).")
    scale = float(pr.cfg.get("preview_scale", 0.5)) if preview else 1.0
    W = int(tl.W * scale) // 2 * 2
    H = int(tl.H * scale) // 2 * 2
    if preview:
        enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "27", "-pix_fmt", "yuv420p"]
    else:
        enc = ["-c:v", "libx264", "-preset", pr.cfg.get("x264_preset", "medium"),
               "-crf", str(pr.cfg.get("crf", 18)), "-pix_fmt", "yuv420p", "-profile:v", "high"]
    mode = "preview" if preview else "final"
    cdir = pr.work / "render" / mode
    cdir.mkdir(parents=True, exist_ok=True)
    chunks = split_chunks(tl, float(pr.cfg.get("chunk_seconds", 60)))
    vlist, alist = [], []
    info(f"Render {mode}: {tc(tl.duration)} • {len(tl.video)} item • {len(chunks)} chunk • {W}x{H}@{tl.fps:g}")
    for n, ch in enumerate(chunks, 1):
        c0 = ch[0]["start"] / tl.fps
        c1 = (ch[-1]["start"] + ch[-1]["frames"]) / tl.fps
        ovs = [o for o in tl.overlays if o["at"] < c1 and o["at"] + tl.overlay_len(o) > c0]
        key = sha({"v": 4, "items": [item_key(i) for i in ch], "ns": [item_samples(tl, i) for i in ch],
                   "ovs": [{**{k: v for k, v in o.items() if k != "at"}, "rel": round(o["at"] - c0, 4)} for o in ovs], "W": W, "H": H, "fps": tl.fps, "fit": tl.fit, "enc": enc,
                   "src": [file_sig(tl.src(i, preview)) for i in ch if i["type"] != "color"],
                   "ovsrc": [file_sig(tl.overlay_file(o)) for o in ovs], "cat": [tl.has_audio(i) for i in ch]})
        vf, af = cdir / f"{key}.mp4", cdir / f"{key}.wav"
        status = "cache"
        if not (vf.exists() and af.exists()):
            status = "render"
            render_chunk(tl, ch, preview, vf, af, W, H, enc)
        info(f"  [{n}/{len(chunks)}] {tc(c0, ms=False)}–{tc(c1, ms=False)} {status}")
        vlist.append(vf)
        alist.append(af)
    tmp = pr.work / "render" / f"_mux_{label}"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "v.txt").write_text("".join(f"file '{p.resolve()}'\n" for p in vlist))
    (tmp / "a.txt").write_text("".join(f"file '{p.resolve()}'\n" for p in alist))
    video = tmp / "video.mp4"
    dialog = tmp / "dialog.wav"
    ffmpeg(["-f", "concat", "-safe", "0", "-i", tmp / "v.txt", "-c", "copy", video])
    ffmpeg(["-f", "concat", "-safe", "0", "-i", tmp / "a.txt", "-c", "copy", dialog])
    info("  mix audio …")
    mix = tmp / "mix.wav"
    mix_audio(tl, dialog, mix, preview)
    target = float(pr.cfg.get("target_lufs", -16))
    meas = loudnorm_measure(mix, target)
    info(f"  loudness {meas['input_i']} → {target} LUFS")
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg(["-i", video, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
            "-af", loudnorm_filter(meas, target) + f",aresample={SR}", "-c:a", "aac",
            "-b:a", "128k" if preview else "320k", "-movflags", "+faststart", "-shortest", out])
    shutil.rmtree(tmp)
    info(f"✓ {out}  ({out.stat().st_size / 1e6:.1f} MB)")


def cmd_render(a):
    pr = Project(a.project)
    tl = load_timeline(pr, a.timeline)
    preview = not a.final
    label = "preview" if preview else "final"
    if a.range:
        s, e = a.range.split("-")
        t0, t1 = parse_time(s), parse_time(e)
        tl = sub_timeline(tl, t0, t1)
        label += f"_{tc(t0, ms=False).replace(':', '')}-{tc(t1, ms=False).replace(':', '')}"
    out = Path(a.out) if a.out else (pr.review if preview else pr.out) / f"{pr.slug}_{label}.mp4"
    do_render(pr, tl, preview, out, label)


def cmd_clean(a):
    pr = Project(a.project)
    d = pr.work / "render"
    if d.exists():
        size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) / 1e9
        shutil.rmtree(d)
        info(f"✓ cache render dihapus ({size:.2f} GB)")


# ---------------------------------------------------------------- stills / storyboard

def still_at(tl: TL, t: float, dst: Path, W: int, H: int, label: str = ""):
    it = tl.at_time(t)
    if not it:
        die("Timeline kosong")
    local = t - it["start"] / tl.fps
    fit = it.get("fit", tl.fit)
    geo = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:-1:-1" if fit == "fit"
           else f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}")
    inputs, chains = [], []
    if it["type"] == "color":
        inputs = ["-f", "lavfi", "-i", f"color=c={it.get('color', 'black')}:s={W}x{H}:d=1"]
        chains.append("[0:v]setpts=PTS-STARTPTS[b]")
    elif it["type"] == "image":
        inputs = ["-i", tl.src(it, True)]
        z = 1 + float(it.get("zoom", 0)) * (local / (it["frames"] / tl.fps))
        chains.append(f"[0:v]{geo},scale=iw*{z:.4f}:ih*{z:.4f},crop={W}:{H},setpts=PTS-STARTPTS[b]")
    else:
        st = it["in"] + local * float(it.get("speed", 1.0))
        inputs = ["-ss", f"{st:.3f}", "-i", tl.src(it, False)]
        chains.append(f"[0:v]{geo}" + (f",{it['vf']}" if it.get("vf") else "") + ",setpts=PTS-STARTPTS[b]")
    cur, k = "b", 1
    for o in tl.overlays:
        o0 = o["at"]
        o1 = o0 + tl.overlay_len(o) - float(o.get("offset", 0))
        if not (o0 <= t < o1):
            continue
        f = tl.overlay_file(o)
        if f.suffix.lower() in IMAGE_EXT:
            inputs += ["-i", f]
        else:
            inputs += ["-ss", f"{t - o0 + float(o.get('offset', 0)):.3f}", "-i", f]
        chains.append(f"[{k}:v]scale={W}:{H},format=yuva420p,setpts=PTS-STARTPTS[o{k}]")
        chains.append(f"[{cur}][o{k}]overlay=format=auto[x{k}]")
        cur, k = f"x{k}", k + 1
    if label:
        chains.append(f"[{cur}]drawtext={font_opt()}text='{esc_text(label)}':x=8:y=8:fontsize={max(14, H // 22)}:"
                      f"fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=6[lab]")
        cur = "lab"
    chains.append(f"[{cur}]format=yuv420p[fin]")
    cur = "fin"
    dst.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg([*inputs, "-filter_complex", ";".join(chains), "-map", f"[{cur}]", "-frames:v", "1", "-q:v", "3",
            "-update", "1", dst])


def cmd_stills(a):
    pr = Project(a.project)
    tl = load_timeline(pr, a.timeline)
    W, H = tl.W, tl.H
    if a.half:
        W, H = W // 2 // 2 * 2, H // 2 // 2 * 2
    times = [parse_time(x) for x in (a.at or [])]
    for gid in a.items or []:
        it = next((i for i in tl.video if i["id"] == gid), None)
        if not it:
            die(f"Item tidak ada: {gid}")
        times.append((it["start"] + it["frames"] / 2) / tl.fps)
    for o in tl.overlays:
        if a.overlays:
            times.append(o["at"] + min(tl.overlay_len(o) * 0.6, 2.0))
    if not times:
        die("Beri --at <waktu>, --items <id>, atau --overlays")
    outdir = pr.review / "stills"
    for t in times:
        dst = outdir / f"still_{tc(t).replace(':', '').replace('.', '_')}.jpg"
        still_at(tl, t, dst, W, H)
        info(f"✓ {dst.relative_to(pr.dir)}  @ {tc(t)}")


def cmd_storyboard(a):
    pr = Project(a.project)
    tl = load_timeline(pr, a.timeline)
    if a.range:
        s, e = a.range.split("-")
        tl = sub_timeline(tl, parse_time(s), parse_time(e))
    W = 480
    H = int(W * tl.H / tl.W) // 2 * 2
    tmp = pr.work / "storyboard_tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    for n, it in enumerate(tl.video):
        t = (it["start"] + it["frames"] / 2) / tl.fps
        lab = f"{it['id']} {tc(it['start'] / tl.fps, ms=False)} ({it['frames'] / tl.fps:.1f}s)"
        if it.get("label"):
            lab += " " + it["label"][:30]
        still_at(tl, t, tmp / f"s_{n:05d}.jpg", W, H, lab)
    cols = a.cols
    rows = max(1, min(a.rows, math.ceil(len(tl.video) / cols)))
    outdir = pr.review / "storyboard"
    shutil.rmtree(outdir, ignore_errors=True)
    outdir.mkdir(parents=True)
    ffmpeg(["-framerate", "1", "-reinit_filter", "0", "-i", tmp / "s_%05d.jpg", "-vf", f"tile={cols}x{rows}:padding=4:margin=4:color=0x222222",
            "-q:v", "3", "-fps_mode", "passthrough", outdir / "board_%02d.jpg"])
    shutil.rmtree(tmp)
    info(f"✓ storyboard → {outdir.relative_to(pr.dir)}/ ({len(tl.video)} item)")


# ---------------------------------------------------------------- exports

def cmd_subs(a):
    pr = Project(a.project)
    tl = load_timeline(pr, a.timeline)
    words = []
    for it in tl.video:
        if not tl.has_audio(it) or not pr.transcript_path(it["clip"]).exists():
            continue
        sp = float(it.get("speed", 1.0))
        t0 = it["start"] / tl.fps
        for w in load_words(pr, it["clip"]):
            if w["start"] >= it["in"] and w["end"] <= it["out"]:
                words.append({"w": w["w"], "s": t0 + (w["start"] - it["in"]) / sp, "e": t0 + (w["end"] - it["in"]) / sp})
    for o in tl.voiceover:
        clip = o.get("clip")
        if not clip or not pr.transcript_path(clip).exists():
            continue
        sp = float(o.get("speed", 1.0))
        i0, i1 = o.get("in", 0), o.get("out", 1e9)
        for w in load_words(pr, clip):
            if w["start"] >= i0 and w["end"] <= i1:
                words.append({"w": w["w"], "s": o["at"] + (w["start"] - i0) / sp, "e": o["at"] + (w["end"] - i0) / sp})
    words.sort(key=lambda w: w["s"])
    cues, cur = [], []
    for w in words:
        if cur and (len(" ".join(x["w"] for x in cur + [w])) > a.max_chars or w["e"] - cur[0]["s"] > a.max_dur
                    or w["s"] - cur[-1]["e"] > 0.6):
            cues.append(cur)
            cur = []
        cur.append(w)
    if cur:
        cues.append(cur)

    def srt_t(s):
        ms = int(round(s * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    out = Path(a.out) if a.out else pr.out / f"{pr.slug}.srt"
    lines = []
    for n, c in enumerate(cues, 1):
        end = c[-1]["e"] + 0.15
        if n < len(cues):
            end = min(end, cues[n][0]["s"] - 0.02)
        lines += [str(n), f"{srt_t(c[0]['s'])} --> {srt_t(max(end, c[0]['s'] + 0.3))}", " ".join(x["w"] for x in c), ""]
    out.write_text("\n".join(lines))
    info(f"✓ {len(cues)} subtitle → {out}")


def cmd_edl(a):
    """Ekspor CMX3600 EDL (track video) untuk finishing di DaVinci Resolve / Premiere."""
    pr = Project(a.project)
    tl = load_timeline(pr, a.timeline)
    fps = tl.fps
    rec0 = int(3600 * round(fps))  # rekaman mulai 01:00:00:00
    lines = [f"TITLE: {pr.slug}", "FCM: NON-DROP FRAME", ""]
    n = 0
    for it in tl.video:
        if it["type"] == "color":
            continue
        n += 1
        c = tl.cat.get(it["clip"], {})
        base = 0
        if c.get("timecode"):
            hh, mm, ss, ff = [int(x) for x in re.split(r"[:;]", c["timecode"])]
            base = ((hh * 60 + mm) * 60 + ss) * int(round(fps)) + ff
        sp = float(it.get("speed", 1.0))
        s_in = base + int(round(it["in"] * fps))
        s_out = s_in + int(round(it["frames"] * sp))
        r_in = rec0 + it["start"]
        r_out = r_in + it["frames"]
        reel = "AX"
        lines.append(f"{n:03d}  {reel:<8} V     C        {tc_frames(s_in, fps)} {tc_frames(s_out, fps)} "
                     f"{tc_frames(r_in, fps)} {tc_frames(r_out, fps)}")
        lines.append(f"* FROM CLIP NAME: {Path(it['clip']).name}")
        if abs(sp - 1) > 1e-6:
            lines.append(f"M2   {reel:<8}       {fps * sp:05.1f}                {tc_frames(s_in, fps)}")
        if it.get("label"):
            lines.append(f"* COMMENT: {it['label']}")
        lines.append("")
    out = Path(a.out) if a.out else pr.out / f"{pr.slug}.edl"
    out.write_text("\n".join(lines))
    info(f"✓ {n} event → {out}")


def cmd_info(a):
    pr = Project(a.project)
    tl = load_timeline(pr, a.timeline)
    print(f"Timeline {pr.slug}: {tc(tl.duration)} • {len(tl.video)} item video • {len(tl.overlays)} overlay • "
          f"{len(tl.voiceover)} VO • {len(tl.music)} musik • {tl.W}x{tl.H}@{tl.fps:g}")
    secs = {s["at"]: s["title"] for s in tl.data.get("sections", [])}
    for it in tl.video:
        t = it["start"] / tl.fps
        for at in [x for x in sorted(secs) if parse_time(x) <= t]:
            print(f"── {secs.pop(at)}")
        src = it.get("clip", it.get("color", ""))
        rng = f"{tc(it['in'])}–{tc(it['out'])}" if it["type"] == "video" else ""
        sp = f" x{it['speed']}" if it.get("speed", 1) != 1 else ""
        print(f"  {tc(t)}  {it['id']:<8} {it['frames'] / tl.fps:6.2f}s  {src} {rng}{sp}  {it.get('label', '')}")
    if a.check:
        problems = []
        for it in tl.video:
            if it["type"] == "video":
                c = tl.cat.get(it["clip"])
                if not c:
                    problems.append(f"{it['id']}: klip tidak ada di katalog ({it['clip']})")
                elif it["out"] > c.get("duration", 1e9) + 0.05:
                    problems.append(f"{it['id']}: out {it['out']} > durasi klip {c['duration']:.2f}")
        for o in tl.overlays:
            if not tl.overlay_file(o).exists():
                problems.append(f"overlay belum dirender: {tl.overlay_file(o)}")
        print("\n".join(["Masalah:"] + problems) if problems else "✓ timeline valid")


# ---------------------------------------------------------------- gfx (Remotion)

def cmd_gfx(a):
    pr = Project(a.project)
    f = pr.dir / "gfx.json"
    if not f.exists():
        die("gfx.json tidak ada di proyek")
    spec = json.loads(f.read_text())
    rd = remotion_dir()
    if not (rd / "node_modules" / "remotion").exists():
        die(f"Remotion belum di-install: cd {rd} && npm install")
    fps = pr.cfg.get("fps", 25)
    W, H = pr.cfg.get("width", 1920), pr.cfg.get("height", 1080)
    outdir = pr.work / "gfx"
    outdir.mkdir(parents=True, exist_ok=True)
    pub = rd / "public" / "projects" / pr.slug
    theme = spec.get("theme", {})
    browser = os.environ.get("REMOTION_BROWSER_EXECUTABLE")
    for g in spec.get("items", []):
        if a.only and g["id"] not in a.only:
            continue
        props = {**g.get("props", {}), "theme": {**theme, **g.get("props", {}).get("theme", {})},
                 "duration": g.get("duration", 5), "fps": fps, "width": W, "height": H}

        def fix_assets(v):
            if isinstance(v, str) and v.startswith("assets/"):
                src = pr.dir / v
                if not src.exists():
                    die(f"Aset tidak ada: {src}")
                dst = pub / Path(v).name
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
                    shutil.copy2(src, dst)
                return f"projects/{pr.slug}/{Path(v).name}"
            if isinstance(v, dict):
                return {k: fix_assets(x) for k, x in v.items()}
            if isinstance(v, list):
                return [fix_assets(x) for x in v]
            return v
        props = fix_assets(props)
        pf = outdir / f"{g['id']}.props.json"
        pf.write_text(json.dumps(props, ensure_ascii=False))
        extra = ["--browser-executable", browser] if browser else []
        if a.still is not None:
            frame = int(parse_time(a.still) * fps) if a.still else int(props["duration"] * fps * 0.6)
            dst = pr.review / "stills" / f"gfx_{g['id']}.png"
            dst.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["npx", "remotion", "still", "src/index.ts", g["composition"], str(dst),
                            f"--props={pf}", f"--frame={frame}", "--log=error", *extra], cwd=rd, check=True)
            info(f"✓ still {dst.relative_to(pr.dir)}")
            continue
        dst = outdir / f"{g['id']}.mov"
        key = sha([g, theme, fps, W, H])
        stamp = outdir / f"{g['id']}.hash"
        if dst.exists() and stamp.exists() and stamp.read_text() == key and not a.force:
            info(f"  {g['id']} — cache")
            continue
        info(f"  {g['id']} ({g['composition']}) …")
        subprocess.run(["npx", "remotion", "render", "src/index.ts", g["composition"], str(dst), f"--props={pf}",
                        "--codec=prores", "--prores-profile=4444", "--pixel-format=yuva444p10le",
                        "--image-format=png", "--log=error", *extra], cwd=rd, check=True)
        stamp.write_text(key)
        info(f"✓ {dst.relative_to(pr.dir)}")


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(prog="vedit", description="Toolkit editing video panjang — kolaborasi manusia + Claude.")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("doctor", help="cek ffmpeg/whisper/remotion")
    p.set_defaults(fn=cmd_doctor)

    p = sp.add_parser("new", help="buat proyek baru dari template")
    p.add_argument("slug")
    p.add_argument("--type", required=True, choices=["event", "travel", "headliner"])
    p.add_argument("--vertical", action="store_true", help="9:16 (1080x1920)")
    p.set_defaults(fn=cmd_new)

    p = sp.add_parser("ingest", help="katalog footage + proxy + scene + contact sheet + audio 16k")
    p.add_argument("project")
    p.add_argument("--only", help="glob, mis. 'day1/*'")
    p.add_argument("--no-proxy", action="store_true")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_ingest)

    p = sp.add_parser("transcribe", help="transkrip kata-per-kata (whisper.cpp)")
    p.add_argument("project")
    p.add_argument("--lang")
    p.add_argument("--model")
    p.add_argument("--threads", type=int, default=max(1, (os.cpu_count() or 4) - 1))
    p.add_argument("--only")
    p.add_argument("--all", action="store_true", help="termasuk klip yang audionya sangat pelan")
    p.add_argument("--force", action="store_true")
    p.add_argument("--extra", nargs=argparse.REMAINDER, help="argumen tambahan untuk whisper-cli")
    p.set_defaults(fn=cmd_transcribe)

    p = sp.add_parser("find", help="cari kata/kalimat di semua transkrip (regex)")
    p.add_argument("project")
    p.add_argument("pattern")
    p.set_defaults(fn=cmd_find)

    p = sp.add_parser("tighten", help="rapatkan jeda ucapan → item timeline")
    p.add_argument("project")
    p.add_argument("clip")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--max-gap", type=float, default=0.8, help="jeda di atas ini dipangkas")
    p.add_argument("--gap", type=float, default=0.7, help="panjang jeda setelah dipangkas")
    p.add_argument("--speed", type=float, default=1.0, help="1.1–1.2 = 10–20%% lebih cepat (nada tetap)")
    p.add_argument("--open-seconds", type=float, default=60.0, help="durasi pembuka yang lebih rapat")
    p.add_argument("--open-gap", type=float, default=0.4)
    p.add_argument("--open-speed", type=float, help="default = --speed")
    p.add_argument("--pad", type=float, default=0.08)
    p.add_argument("--at", default="0", help="posisi awal (khusus voiceover)")
    p.add_argument("--prefix", default="t")
    p.add_argument("--out")
    p.add_argument("--render", help="tulis preview audio (wav)")
    p.set_defaults(fn=cmd_tighten)

    p = sp.add_parser("clean-audio", help="highpass + denoise opsional + loudnorm 2-pass")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--lufs", type=float, default=-16)
    p.add_argument("--denoise", type=float, help="kekuatan afftdn (mis. 12)")
    p.set_defaults(fn=cmd_clean_audio)

    p = sp.add_parser("key", help="buang latar hijau aset (Gemini) → PNG transparan")
    p.add_argument("inputs", nargs="+")
    p.add_argument("--outdir", required=True)
    p.add_argument("--color", default="00B140")
    p.add_argument("--similarity", type=float, default=0.22)
    p.add_argument("--blend", type=float, default=0.08)
    p.set_defaults(fn=cmd_key)

    p = sp.add_parser("beats", help="deteksi BPM, beat, bar, perubahan energi musik")
    p.add_argument("input")
    p.add_argument("--out")
    p.add_argument("--min-bpm", type=int, default=70)
    p.add_argument("--max-bpm", type=int, default=180)
    p.set_defaults(fn=cmd_beats)

    p = sp.add_parser("ab", help="video pilihan A/B berlabel (<30 MB) untuk dipilih manusia")
    p.add_argument("output")
    p.add_argument("options", nargs="+", help="'A take 1=path/file.wav@0:10-0:25'")
    p.add_argument("--crf", type=int, default=30)
    p.set_defaults(fn=cmd_ab)

    p = sp.add_parser("info", help="ringkasan timeline (+ --check validasi)")
    p.add_argument("project")
    p.add_argument("--timeline")
    p.add_argument("--check", action="store_true")
    p.set_defaults(fn=cmd_info)

    p = sp.add_parser("stills", help="still preview di frame kunci (gerbang persetujuan)")
    p.add_argument("project")
    p.add_argument("--timeline")
    p.add_argument("--at", nargs="*")
    p.add_argument("--items", nargs="*")
    p.add_argument("--overlays", action="store_true", help="still untuk tiap overlay/grafis")
    p.add_argument("--half", action="store_true")
    p.set_defaults(fn=cmd_stills)

    p = sp.add_parser("storyboard", help="grid thumbnail semua item timeline")
    p.add_argument("project")
    p.add_argument("--timeline")
    p.add_argument("--range", help="mis. 10:00-15:00")
    p.add_argument("--cols", type=int, default=5)
    p.add_argument("--rows", type=int, default=6)
    p.set_defaults(fn=cmd_storyboard)

    p = sp.add_parser("render", help="render preview (½ res, proxy) atau --final")
    p.add_argument("project")
    p.add_argument("--timeline")
    p.add_argument("--final", action="store_true")
    p.add_argument("--range", help="render sebagian, mis. 05:00-08:30")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_render)

    p = sp.add_parser("clean", help="hapus cache chunk render")
    p.add_argument("project")
    p.set_defaults(fn=cmd_clean)

    p = sp.add_parser("subs", help="SRT dari transkrip mengikuti timeline")
    p.add_argument("project")
    p.add_argument("--timeline")
    p.add_argument("--out")
    p.add_argument("--max-chars", type=int, default=42)
    p.add_argument("--max-dur", type=float, default=3.5)
    p.set_defaults(fn=cmd_subs)

    p = sp.add_parser("edl", help="ekspor CMX3600 EDL untuk DaVinci/Premiere")
    p.add_argument("project")
    p.add_argument("--timeline")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_edl)

    p = sp.add_parser("gfx", help="render grafis Remotion dari gfx.json (ProRes 4444 alpha)")
    p.add_argument("project")
    p.add_argument("--only", nargs="*")
    p.add_argument("--still", nargs="?", const="", help="render still saja (opsional: waktu)")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_gfx)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
