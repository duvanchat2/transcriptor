# PROMPT DEL AGENTE — Pipeline completo de edición de video
# Dar esto al agente AL INICIO de cada sesión nueva

---

## PASO 0 — Leer ANTES de hacer cualquier cosa

Lee estos archivos en orden y confirma cada uno en voz alta:

1. `edit/project.md`         → video fuente exacto, rutas, estado actual
2. `edit/ERRORS.md`          → di "Entendido, evitaré: X" por cada error registrado
3. `edit/hyperframes/subtitles-comp/CLAUDE.md` → reglas de operación HyperFrames

Si alguno no existe, dímelo. No continues sin leerlos.

---

## EL PIPELINE — 4 fases en orden estricto

```
FASE 1: Cortar silencios
FASE 2: Transcribir y limpiar errores
FASE 3: Subtítulos sincronizados
FASE 4: HyperFrames — motion graphics y animaciones
```

No saltes fases. No combines fases. Confirma conmigo al terminar cada una.

---

## FASE 1 — Cortar silencios

**Objetivo:** Eliminar silencios y tomas fallidas. Producir `base_<video>.mp4` limpio.

```bash
# 1. Obtener dimensiones reales del video fuente
ffprobe -v quiet -print_format json -show_streams "videos_editar/<video>.mp4" \
  | python -c "import json,sys; s=json.load(sys.stdin)['streams'][0]; print(s['width'],'x',s['height'])"

# 2. Cortar silencios
PYTHONIOENCODING=utf-8 python helpers/silence_cut.py "videos_editar/<video>.mp4"

# 3. Generar base limpia (sin subtítulos todavía)
PYTHONIOENCODING=utf-8 python helpers/render.py \
  --edl edit/edl_<video>.json \
  --no-subtitles \
  --out edit/base_<video>.mp4
```

**Verificación obligatoria antes de continuar:**
```bash
ffmpeg -ss 3 -i edit/base_<video>.mp4 -vframes 1 -q:v 2 edit/check_fase1.jpg
```
Mostrar `check_fase1.jpg` al usuario y esperar confirmación: _"¿Los cortes se ven bien?"_

---

## FASE 2 — Transcribir y limpiar errores

**Objetivo:** Transcripción word-level del video YA CORTADO (base, no fuente).

**Regla crítica:** Transcribir `base_<video>.mp4`, NO el video fuente original.
Los timestamps deben corresponder a la timeline del video editado.

```bash
# Extraer audio del base (mono 16kHz para AssemblyAI)
ffmpeg -i edit/base_<video>.mp4 \
  -ac 1 -ar 16000 -sample_fmt s16 \
  edit/audio_<video>.wav

# Transcribir con AssemblyAI universal-2
PYTHONIOENCODING=utf-8 python helpers/transcribe.py edit/audio_<video>.wav
# Output: edit/transcripts/<video>.json
```

**Verificación del transcript:**
```python
import json
from pathlib import Path
t = json.loads(Path('edit/transcripts/<video>.json').read_text(encoding='utf-8'))
words = t.get('words', [])
for w in words[:10]:
    print(f"{w['start']/1000:.2f}s  {w['text']}")
```
Mostrar output al usuario: _"¿Estas son las primeras palabras del video editado?"_

**Importante:** Si el transcript tiene errores de reconocimiento, corregirlos a mano en el JSON antes de continuar.

---

## FASE 3 — Subtítulos sincronizados

**Objetivo:** Subtítulos animados como WebM con alpha, compuestos sobre base.mp4.

**NOTA SOBRE REMAP:** Como transcribiste el `base_<video>.mp4` (no el fuente),
los timestamps ya están en la timeline correcta. NO necesitas remap.
Verificar que el primer timestamp del transcript sea < 5s.

```bash
# Generar composición HyperFrames de subtítulos
PYTHONIOENCODING=utf-8 python helpers/gen_subtitles_hf.py \
  --transcript edit/transcripts/<video>.json \
  --out        edit/hyperframes/subtitles-comp/index.html \
  --words-per-cue 2 \
  --font-size 38

# Validar — OBLIGATORIO antes de renderizar
cd edit/hyperframes/subtitles-comp
npx hyperframes lint
# Si hay errores → corregir → lint de nuevo → solo continuar con 0 errores

# Preview visual ANTES del render
npx hyperframes preview
# Abrir http://localhost:3002 y confirmar con el usuario

# Renderizar a WebM con alpha — NUNCA MP4
npx hyperframes render --format webm --out ../../clips_hf/subtitles.webm

# Verificar alpha
ffprobe -v quiet -show_streams ../../clips_hf/subtitles.webm | grep pix_fmt
# Debe mostrar: yuva420p
```

**Calcular offset y compositar:**
```bash
# Obtener altura del video base
ffprobe -v quiet -print_format json -show_streams edit/base_<video>.mp4 \
  | python -c "import json,sys; s=json.load(sys.stdin)['streams'][0]; print(s['height'] - 1080)"
# Ese número es OFFSET_Y

ffmpeg -i edit/base_<video>.mp4 \
       -i edit/clips_hf/subtitles.webm \
  -filter_complex "[0:v][1:v]overlay=x=0:y=OFFSET_Y:format=auto[vout]" \
  -map "[vout]" -map "0:a" \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart \
  edit/final_subs_<video>.mp4
```

**Verificación:**
```bash
ffmpeg -ss 5 -i edit/final_subs_<video>.mp4 -vframes 1 -q:v 2 edit/check_fase3.jpg
```
Mostrar `check_fase3.jpg`. Esperar OK del usuario antes de avanzar a Fase 4.

---

## FASE 4 — HyperFrames: motion graphics y animaciones

**Objetivo:** Hook visual, lower thirds, karaoke captions, CTA final.

**Referencia de estilo:** may-shorts-18 y may-shorts-19 del student-kit.

### Reglas de animación:
- Entrances con `gsap.from()` únicamente
- Easing: `power3.out`, `expo.out`, `back.out(1.4)` para entradas; `power2.in` para salidas
- Timeline anchor al final de cada tl para evitar black frame flash:
  ```javascript
  tl.to({}, { duration: SLOT_DURATION }, 0);
  ```
- data-track-index >= 20 para captions

### Qué crear (en orden):
1. Hook visual (primeros 2-3s) — texto grande, fondo oscuro
2. Lower third — nombre/handle, bottom-left, ~1.5s entrada, 3s duración
3. Captions karaoke — 2 palabras/cue, palabras clave con color
4. CTA final — últimos 3s

```bash
# Workflow
cd edit/hyperframes/motion-comp
npx hyperframes lint          # después de CADA cambio
npx hyperframes preview       # antes del render
npx hyperframes render --out ../../clips_hf/motion.webm

# Composite final
ffmpeg -i edit/final_subs_<video>.mp4 \
       -i edit/clips_hf/motion.webm \
  -filter_complex "[0:v][1:v]overlay=x=0:y=OFFSET_Y[vout]" \
  -map "[vout]" -map "0:a" \
  -c:v libx264 -preset slow -crf 18 \
  -c:a copy edit/final_<video>.mp4
```

---

## CUANDO COMETAS UN ERROR

1. Para lo que estás haciendo.
2. Agrega entrada a `edit/ERRORS.md`.
3. Di en voz alta cuál fue el error y la regla nueva.
4. Corrige.

---

## REGLAS NO NEGOCIABLES

| Regla | Por qué |
|-------|---------|
| Transcribir el BASE, no el fuente | Para que timestamps coincidan sin remap |
| WebM siempre para overlays, nunca MP4 | MP4 sin alpha tapa el video con rectángulo blanco |
| Lint después de CADA cambio a .html | No al final — después de cada cambio |
| preview antes del render final | El render es costoso; el preview es gratis |
| Borrar intermedios antes de re-renderear | Evita que el caché tape los cambios |
| Path() siempre para rutas, nunca f-strings con \ | \f se interpreta como form-feed |
| Screenshot después de cada fase | No declarar éxito sin ver el resultado |
| data-track-index >= 20 para captions | Requisito del framework HyperFrames |
| Timeline anchor al final de cada tl | Evita black frame flash |
| Verificar pix_fmt=yuva420p antes de compositar | Confirma que el WebM tiene canal alpha |

---

## REGLA DE AUTO-REVISIÓN — claude-video-vision

**Después de cada render, ANTES de reportar nada, el agente se auto-revisa solo.**

No preguntar si se ve bien. Verlo primero.

```bash
# Después de Fase 3 (subtítulos):
/watch-video edit/final_subs_<video>.mp4 "Revisa estos 4 puntos y da veredicto APROBADO o RECHAZADO:
1. ¿El tamaño del texto es legible sin ser demasiado grande?
2. ¿Los subtítulos están en la zona inferior pero NO pegados al borde negro?
3. ¿El recuadro detrás del texto se integra bien o es muy llamativo?
4. ¿Los subtítulos aparecen sincronizados con el audio (verificar segundo 3, 10 y 30)?"

# Después de Fase 4 (motion graphics):
/watch-video edit/final_<video>.mp4 "Revisa estos 4 puntos y da veredicto APROBADO o RECHAZADO:
1. ¿El hook visual de los primeros 3s se ve impactante y legible?
2. ¿Los motion graphics no tapan la cara del presentador?
3. ¿El CTA final es visible y está bien posicionado?
4. ¿Hay frames negros o parpadeos entre escenas?"
```

**Flujo:**
```
render → /watch-video → RECHAZADO → corregir → re-render → /watch-video → APROBADO → reportar
```

Solo contactar al usuario cuando el veredicto es APROBADO.
Si después de 3 intentos sigue RECHAZADO en el mismo punto → escalar con el error específico.

---

## AL CERRAR LA SESIÓN

1. ¿Cometí errores esta sesión? → verificar que están en ERRORS.md
2. ¿Hay algo que casi salió mal pero lo atrapé? → agregarlo igual
3. Actualizar `edit/project.md` con el estado actual de cada fase
4. Confirmar: "Sesión cerrada. Pipeline en fase X. ERRORS.md actualizado."
