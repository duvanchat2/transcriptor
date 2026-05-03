"""
render_composite.py
───────────────────
Composita base.mp4 + clips HyperFrames → final_hf.mp4
Incluye loudness normalization a -14 LUFS.

Uso:
    PYTHONIOENCODING=utf-8 python edit/render_composite.py
"""
import subprocess
import sys
from pathlib import Path

BASE   = Path("C:/Users/duvan/OneDrive/Documentos/transcriptor")
EDIT   = BASE / "edit"

BASE_MP4  = EDIT / "base_hf.mp4"
OUT_MP4   = EDIT / "final_hf.mp4"
PRENORM   = EDIT / "final_hf.prenorm.mp4"

# Overlays HyperFrames: (archivo, start_s, end_s o None=hasta el final)
HF_OVERLAYS = [
    (EDIT / "clips_hf/subtitles.mp4", 0, None),  # subtítulos todo el video
    # (EDIT / "clips_hf/hook.mp4",    0, 2.58),  # descomentar cuando exista
    # (EDIT / "clips_hf/outro.mp4",  55, None),  # descomentar cuando exista
]

TARGET_LUFS = -14
TARGET_TP   = -1


def srt_posix(path: Path) -> str:
    return path.resolve().as_posix().replace(":", r"\:")


def build_composite(overlays):
    """Construye inputs y filter_complex para los overlays activos."""
    active = [(p, s, e) for p, s, e in overlays if p.exists()]
    if not active:
        print("[WARN] No hay clips HyperFrames. Solo se normalizará el audio.")
        return [], "", "0:v"

    inputs = []
    for p, *_ in active:
        inputs += ["-i", str(p)]
        print(f"  overlay: {p.name}")

    parts = []
    prev = "[0:v]"
    for i, (p, start_s, end_s) in enumerate(active):
        in_pad  = f"[{i+1}:v]"
        out_pad = "[vout]" if i == len(active) - 1 else f"[v{i}]"
        if end_s is None:
            enable = f"enable='gte(t,{start_s})'"
        else:
            enable = f"enable='between(t,{start_s},{end_s})'"
        parts.append(f"{prev}{in_pad}overlay=format=auto:{enable}{out_pad}")
        prev = out_pad

    return inputs, ";".join(parts), "[vout]"


def run(cmd):
    print("$", " ".join(str(x) for x in cmd[:6]), "...")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        sys.exit(f"[ERROR] ffmpeg falló (código {result.returncode})")


def loudnorm(src: Path, dst: Path):
    """Dos pasadas de loudnorm."""
    print(f"\n[loudnorm] midiendo {src.name}...")
    r = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-i", str(src),
         "-af", f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA=11:print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    # Parsear JSON de loudnorm desde stderr
    import re, json
    m = re.search(r"\{[^{}]+\}", r.stderr, re.DOTALL)
    stats = json.loads(m.group()) if m else {}
    i  = stats.get("input_i",  "-14.0")
    tp = stats.get("input_tp", "-1.0")
    lra= stats.get("input_lra","11.0")
    thr= stats.get("input_thresh", "-24.0")
    off= stats.get("target_offset","0.0")
    print(f"  medido: I={i} TP={tp} LRA={lra}")

    print(f"[loudnorm] normalizando → {dst.name}")
    af = (
        f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA=11"
        f":measured_I={i}:measured_TP={tp}:measured_LRA={lra}"
        f":measured_thresh={thr}:offset={off}:linear=true"
    )
    run([
        "ffmpeg", "-y", "-hide_banner",
        "-i", str(src),
        "-af", af,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(dst),
    ])


def main():
    print(f"[composite] {BASE_MP4.name} + overlays → {PRENORM.name}")
    print(f"  base: {BASE_MP4} ({BASE_MP4.stat().st_size/1e6:.1f} MB)")

    overlay_inputs, filter_complex, video_pad = build_composite(HF_OVERLAYS)

    if not overlay_inputs:
        print("[WARN] No hay overlays. Copiando base_hf.mp4 como final.")
        import shutil; shutil.copy(BASE_MP4, OUT_MP4)
        return

    # Detectar dimensiones del video base para posicionar overlay vertical
    import subprocess as _sp, re as _re
    probe = _sp.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "stream=width,height",
         "-select_streams", "v:0", "-of", "csv=p=0", str(BASE_MP4)],
        capture_output=True, text=True
    )
    dims = probe.stdout.strip().split(",")
    base_w, base_h = int(dims[0]), int(dims[1])
    print(f"  video base: {base_w}x{base_h}")

    # Para video vertical: colocar overlay 1920x1080 en la parte inferior
    overlay_h = 1080
    y_offset = max(0, base_h - overlay_h)  # alinear al fondo del frame
    print(f"  overlay y-offset: {y_offset}px (fondo del frame)")

    # Reconstruir filter_complex con posición y offset
    active = [(p, s, e) for p, s, e in HF_OVERLAYS if p.exists()]
    parts2 = []
    prev = "[0:v]"
    for i, (p, start_s, end_s) in enumerate(active):
        in_pad  = f"[{i+1}:v]"
        out_pad = "[vout]" if i == len(active) - 1 else f"[v{i}]"
        enable  = f"enable='gte(t,{start_s})'" if end_s is None else f"enable='between(t,{start_s},{end_s})'"
        parts2.append(f"{prev}{in_pad}overlay=x=0:y={y_offset}:format=auto:{enable}{out_pad}")
        prev = out_pad

    fc = ";".join(parts2)

    run([
        "ffmpeg", "-y", "-hide_banner",
        "-i", str(BASE_MP4),
        *overlay_inputs,
        "-filter_complex", fc,
        "-map", video_pad,
        "-map", "0:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(OUT_MP4),
    ])

    size = OUT_MP4.stat().st_size / 1e6
    print(f"\n✓ {OUT_MP4.name}  ({size:.1f} MB)")


if __name__ == "__main__":
    main()
