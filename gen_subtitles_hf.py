"""
gen_subtitles_hf.py
───────────────────
Genera hyperframes/subtitles-comp/index.html a partir de:
  - transcripts/videoprueba.json  (AssemblyAI, word-level timestamps en SEGUNDOS)
  - edl_videoprueba.json          (segmentos a mantener)

Los timestamps del HTML son en el TIMELINE DE SALIDA (base.mp4), no en el source.
Es decir: si el primer segmento EDL es [0.62–2.58], en el output empieza en t=0.

Uso:
    python edit/gen_subtitles_hf.py
"""
import json
from pathlib import Path

# ── Rutas ──────────────────────────────────────────────────────────────────────
BASE        = Path("C:/Users/duvan/OneDrive/Documentos/transcriptor")
EDIT        = BASE / "edit"
VIDEOS_EDIT = BASE / "videos_editar/edit"

TRANSCRIPT = EDIT / "transcripts/videoprueba.json"   # transcripción del video fuente
EDL        = VIDEOS_EDIT / "edl_videoprueba.json"    # EDL correcto (6 segmentos, Claude+Blender)
OUT_HTML   = EDIT / "hyperframes/subtitles-comp/index.html"

WORDS_PER_CUE = 2
FONT_SIZE     = 17    # canvas 1080×1920
BOTTOM_PX     = 350   # px desde abajo — canvas 1080×1920

# Palabras clave con color especial
HIGHLIGHT = {
    "agentmd":  "#60CDFF",
    "claude":   "#D4A0FF",
    "cursor":   "#D4A0FF",
    "windsurf": "#D4A0FF",
    "copilot":  "#D4A0FF",
}

# ── 1. Cargar transcripción ────────────────────────────────────────────────────
data  = json.loads(TRANSCRIPT.read_text(encoding="utf-8"))
words = [w for w in data.get("words", []) if w.get("type", "word") == "word"]
print(f"[transcript] {len(words)} palabras")

# ── 2. Cargar EDL ─────────────────────────────────────────────────────────────
edl = json.loads(EDL.read_text(encoding="utf-8"))
keeps = [(r["start"], r["end"]) for r in edl["ranges"]]
print(f"[edl] {len(keeps)} segmentos")

# ── 3. Calcular offsets en el timeline de salida ───────────────────────────────
# Cada segmento EDL empieza en su offset acumulado en el output
offsets = []
cursor  = 0.0
for src_start, src_end in keeps:
    offsets.append((src_start, src_end, cursor))
    cursor += src_end - src_start
total_duration = round(cursor, 3)
print(f"[timeline] duración total del output: {total_duration:.2f}s")

def src_to_out(src_t: float) -> float | None:
    """Convierte timestamp source → timestamp output. None si fuera de EDL."""
    for src_s, src_e, out_off in offsets:
        if src_s <= src_t <= src_e:
            return round(out_off + (src_t - src_s), 3)
    return None

# ── 4. Filtrar palabras que caen en EDL y convertir timestamps ─────────────────
filtered = []
for w in words:
    mid = (w["start"] + w["end"]) / 2
    out_start = src_to_out(w["start"])
    out_end   = src_to_out(w["end"])
    if out_start is not None and out_end is not None:
        filtered.append({
            "text":    w["text"],
            "start_s": out_start,
            "end_s":   out_end,
        })

print(f"[filter] {len(filtered)} palabras dentro del EDL")

# ── 5. Agrupar en cues ─────────────────────────────────────────────────────────
cues = []
i = 0
while i < len(filtered):
    group = filtered[i:i + WORDS_PER_CUE]
    start = group[0]["start_s"]
    end   = group[-1]["end_s"]
    dur   = round(max(end - start, 0.2), 3)
    cues.append({"start": start, "dur": dur, "words": [w["text"] for w in group]})
    i += WORDS_PER_CUE

# Recortar duración para evitar overlaps por floating point
for idx in range(len(cues) - 1):
    next_start = cues[idx + 1]["start"]
    cue_end = round(cues[idx]["start"] + cues[idx]["dur"], 4)
    if cue_end >= next_start:
        cues[idx]["dur"] = round(next_start - cues[idx]["start"] - 0.001, 3)

print(f"[cues] {len(cues)} cues generados")

# ── 6. Generar HTML ────────────────────────────────────────────────────────────
def word_span(text: str) -> str:
    color = HIGHLIGHT.get(text.lower().rstrip(".,;:!?¿¡"), "")
    style = f' style="color:{color};"' if color else ""
    return f'<span class="word"{style}>{text}</span>'

def render_cue(cue: dict, idx: int) -> str:
    spans = "\n        ".join(word_span(w) for w in cue["words"])
    return (
        f'    <div class="clip sub-wrap"\n'
        f'         data-start="{cue["start"]}" data-duration="{cue["dur"]}" data-track-index="0"\n'
        f'         id="cue-{idx:03d}">\n'
        f'      {spans}\n'
        f'    </div>\n'
    )

cues_html = "".join(render_cue(c, i + 1) for i, c in enumerate(cues))

html = f"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{
        margin: 0;
        width: 1080px;
        height: 1920px;
        overflow: hidden;
        background: transparent;
      }}
      .sub-wrap {{
        position: absolute;
        bottom: {BOTTOM_PX}px;
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        gap: 8px;
        align-items: center;
        white-space: nowrap;
        pointer-events: none;
        background: transparent;
      }}
      .word {{
        display: inline-block;
        background: transparent;
        color: #FFFFFF;
        font-size: {FONT_SIZE}px;
        font-weight: 400;
        font-family: Arial, sans-serif;
        line-height: 1.2;
        letter-spacing: 0px;
        text-shadow: 1px 1px 4px rgba(0,0,0,0.85), 0 0 8px rgba(0,0,0,0.6);
        will-change: transform, opacity;
      }}
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="{total_duration}"
      data-width="1080"
      data-height="1920"
    >

{cues_html}
    </div>

    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});

      const cues = Array.from(document.querySelectorAll('.clip.sub-wrap'))
        .sort((a, b) => parseFloat(a.dataset.start) - parseFloat(b.dataset.start));

      gsap.set(cues, {{ opacity: 0, y: 24 }});

      cues.forEach(cue => {{
        const start    = parseFloat(cue.dataset.start);
        const duration = parseFloat(cue.dataset.duration);
        const slideIn  = Math.min(0.18, duration * 0.35);
        const slideOut = Math.min(0.14, duration * 0.25);
        const hold     = Math.max(duration - slideIn - slideOut, 0.05);

        // Entra: sube desde abajo + fade in
        tl.to(cue, {{ opacity: 1, y: 0, duration: slideIn, ease: 'power3.out' }}, start)
        // Hold en posición
          .to(cue, {{ opacity: 1, y: 0, duration: hold }}, '>')
        // Sale: sigue subiendo + fade out
          .to(cue, {{ opacity: 0, y: -18, duration: slideOut, ease: 'power2.in' }}, '>');
      }});

      window.__timelines['main'] = tl;
    </script>
  </body>
</html>
"""

OUT_HTML.write_text(html, encoding="utf-8")
print(f"\n✓ Escrito: {OUT_HTML}")
print(f"  {len(cues)} cues · {total_duration:.2f}s de duración")
print(f"\nSiguientes pasos:")
print(f"  cd {OUT_HTML.parent}")
print(f"  npx hyperframes lint")
print(f"  npx hyperframes render -o ../../clips_hf/subtitles.mp4")
