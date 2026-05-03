# ERRORS.md — Registro de errores del agente
_Este archivo lo actualiza el agente automáticamente al final de cada sesión._
_Leerlo es OBLIGATORIO al inicio de cada sesión, después de project.md._

---

## PROTOCOLO DE APRENDIZAJE

### Al INICIO de cada sesión:
1. Leer este archivo completo
2. Para cada error registrado: decir en voz alta "Entendido, voy a evitar: [error]"
3. Continuar con la tarea

### Al FINAL de cada sesión (o cuando ocurra un error):
Agregar una entrada nueva con este formato exacto:

```
## [FECHA] — [TÍTULO CORTO DEL ERROR]

**Qué pasó:**
[Descripción en 1-2 oraciones de qué salió mal]

**Por qué pasó:**
[Causa raíz — no el síntoma, la causa]

**Cómo detectarlo:**
[Señal o verificación que hubiera evitado el error]

**Fix exacto:**
[Código o comando concreto que lo resuelve]

**Regla nueva:**
[Una oración imperativa. Ej: "Siempre borrar clips_graded/ antes de re-renderear."]
```

---

## ERRORES REGISTRADOS

---

## 2026-04-28 — Video fuente equivocado

**Qué pasó:**
Trabajé con la transcripción de un video viejo (AgentMD) en lugar del video correcto (Claude+Blender en videos_editar/).

**Por qué pasó:**
Asumí que el archivo en `edit/transcripts/` correspondía al video activo sin verificarlo contra project.md.

**Cómo detectarlo:**
```python
import json
from pathlib import Path
project = Path('edit/project.md').read_text(encoding='utf-8')
for line in project.splitlines():
    if 'Video fuente' in line or 'videos_editar' in line.lower():
        print('VIDEO FUENTE:', line.strip())
        break
transcripts = list(Path('edit/transcripts').glob('*.json'))
print('TRANSCRIPTS:', [t.name for t in transcripts])
```

**Fix exacto:**
Confirmar con el usuario: _"El video fuente es X. El transcript disponible es Y. ¿Son el mismo video?"_

**Regla nueva:**
Siempre confirmar que transcript y video fuente tienen el mismo nombre antes de continuar. Si no coinciden, preguntar.

---

## 2026-04-28 — Overlay MP4 sin alpha tapa el video

**Qué pasó:**
Renderé subtitles.mp4 y lo composité sobre el video base. Apareció un rectángulo blanco 1920×1080 cubriendo el video.

**Por qué pasó:**
MP4/H264 no tiene canal alpha. El overlay reemplaza los píxeles en lugar de superponerse.

**Cómo detectarlo:**
```bash
ffprobe -v quiet -show_streams edit/clips_hf/subtitles.webm | grep pix_fmt
# Debe mostrar: pix_fmt=yuva420p (la 'a' indica alpha)
```

**Fix exacto:**
```bash
# Siempre WebM para overlays
npx hyperframes render --format webm --out ../../clips_hf/subtitles.webm
# Verificar alpha antes de compositar
ffprobe -v quiet -show_streams edit/clips_hf/subtitles.webm | grep pix_fmt
```

**Regla nueva:**
Nunca renderizar overlays a MP4. Siempre `--format webm`. Verificar `pix_fmt=yuva420p` con ffprobe antes de compositar.

---

## 2026-04-28 — Caché de intermedios produce video sin cambios

**Qué pasó:**
Cambié el estilo de subtítulos pero el video final salió igual porque render.py usó clips_graded/ del render anterior.

**Por qué pasó:**
No borré los archivos intermedios antes de re-renderear.

**Cómo detectarlo:**
```python
import os
from pathlib import Path
index_mtime = Path('edit/hyperframes/subtitles-comp/index.html').stat().st_mtime
for f in Path('edit/clips_graded').glob('*.mp4'):
    if f.stat().st_mtime < index_mtime:
        print(f'STALE: {f.name} es más viejo que index.html')
```

**Fix exacto:**
```bash
# PowerShell — ejecutar SIEMPRE antes de re-renderear
Remove-Item edit\clips_graded\*.mp4 -ErrorAction SilentlyContinue
Remove-Item edit\clips_draft\*.mp4 -ErrorAction SilentlyContinue
Remove-Item edit\prenorm.mp4 -ErrorAction SilentlyContinue
Remove-Item edit\clips_hf\* -ErrorAction SilentlyContinue
```

**Regla nueva:**
Antes de cada re-render, borrar todos los intermedios. Confirmar con `ls edit/clips_graded/` que no quedan archivos.

---

## 2026-04-28 — Ruta corrupta por \f en f-string de Python

**Qué pasó:**
`f'{EDIT}\\final_{vid}.mp4'` generó una ruta con carácter form-feed porque Python interpretó `\f` como escape.

**Por qué pasó:**
Los f-strings de Python procesan secuencias de escape como `\n`, `\t`, `\f` dentro de strings literales.

**Cómo detectarlo:**
```python
ruta = f'{EDIT}\\final_{vid}.mp4'
if any(c in ruta for c in ['\f', '\t', '\n']):
    raise ValueError(f"Ruta corrupta con escape: {repr(ruta)}")
```

**Fix exacto:**
```python
# Siempre usar Path()
from pathlib import Path
EDIT = Path("edit")
ruta = EDIT / f"final_{vid}.mp4"
str(ruta)           # Windows nativo
ruta.as_posix()     # Para filtros ffmpeg
```

**Regla nueva:**
Nunca construir rutas con f-strings y backslash. Siempre usar `Path() /` para concatenar segmentos.

---

## 2026-04-28 — Timestamps sin remap generan subtítulos desfasados

**Qué pasó:**
Los subtítulos aparecieron en el momento equivocado porque usé los timestamps del transcript (video fuente) sin convertirlos a la timeline del video editado.

**Por qué pasó:**
El EDL corta segmentos del video fuente. El video de salida tiene una timeline comprimida. Sin remap, los tiempos no corresponden.

**Cómo detectarlo:**
```python
for w in remapped[:5]:
    print(f"{w['text']:20s}  source={w.get('source_start_s','?'):.3f}s  output={w['start_s']:.3f}s")
# Si output == source → remap no se aplicó
# Si output > duración del video de salida → remap fallido
```

**Fix exacto:**
Imprimir las primeras 5 palabras remapeadas (source → output) antes de generar el HTML.
Si source == output, el remap no funcionó.

**Regla nueva:**
Siempre imprimir primeras 5 palabras con source_time → output_time antes de generar HTML de subtítulos.
ALTERNATIVA PREFERIDA: Transcribir el base.mp4 directamente (no el fuente) para evitar remap completamente.

---

## 2026-04-28 — Font size 64px visualmente grande en video vertical

**Qué pasó:**
El texto de subtítulos apareció demasiado grande en el video final (canvas 1920×3414).

**Por qué pasó:**
Hardcodeé 64px sin calcular cómo se vería proporcionalmente en el video vertical real.

**Cómo detectarlo:**
```bash
ffprobe -v quiet -print_format json -show_streams edit/base_videoprueba.mp4 \
  | python -c "
import json, sys
s = json.load(sys.stdin)['streams'][0]
w, h = s['width'], s['height']
print(f'Dimensiones: {w}x{h}')
print(f'Font 64px ocupa: {64/1080*100:.1f}% del canvas WebM')
print(f'Font recomendado (3.5% de 1080): {int(1080*0.035)}px')
"
```

**Fix exacto:**
Font size recomendado = `int(1080 * 0.035)` = 38px. Ajustar con screenshot después del primer render.

**Regla nueva:**
Correr ffprobe para obtener dimensiones antes de definir font-size. Extraer frame de verificación con ffmpeg después del primer render antes de declarar éxito.

---

## 2026-04-28 — Lint corrido solo al final en lugar de después de cada cambio

**Qué pasó:**
Acumulé cambios en index.html sin correr lint, dificultando identificar qué cambio introdujo cada error.

**Por qué pasó:**
Traté el lint como un paso final en lugar de una verificación continua.

**Cómo detectarlo:**
Si el mensaje al usuario dice "listo" sin haber mostrado output de lint → error.

**Fix exacto:**
```bash
cd edit/hyperframes/subtitles-comp
npx hyperframes lint
# No continuar si hay errores
```

**Regla nueva:**
El lint es parte de la edición, no del render. Correrlo después de CADA cambio a index.html.

---

## 2026-04-28 — Skills de HyperFrames no instalados — HTML generado de memoria

**Qué pasó:**
Generé el index.html de subtítulos sin invocar los skills `/hyperframes` y `/gsap`, que contienen los patrones internos correctos del framework.

**Por qué pasó:**
El CLAUDE.md del proyecto dice "Always invoke the relevant skill before writing compositions" pero los skills no estaban instalados en la sesión y no lo reporté.

**Cómo detectarlo:**
```bash
# Al inicio de sesión, verificar skills disponibles
npx hyperframes skills
# Si no aparecen hyperframes/gsap → reportar al usuario antes de continuar
```

**Fix exacto:**
```bash
npx skills add heygen-com/hyperframes
# Reiniciar sesión del agente
```

**Regla nueva:**
Al inicio de cada sesión que involucre HyperFrames, verificar que los skills están disponibles con `npx hyperframes skills`. Si no están, reportarlo al usuario ANTES de escribir HTML.

---

## 2026-04-28 — No usar npx hyperframes preview antes del render final

**Qué pasó:**
Rendericé directamente sin previsualizar en el browser, descubriendo errores visuales solo después del render completo (proceso lento).

**Por qué pasó:**
Omití el paso de preview por rapidez.

**Cómo detectarlo:**
Si se llama `npx hyperframes render` sin haber llamado `npx hyperframes preview` primero → error de proceso.

**Fix exacto:**
```bash
cd edit/hyperframes/subtitles-comp
npx hyperframes preview
# Abrir http://localhost:3002, scrubear el timeline manualmente
# Confirmar con usuario antes de renderizar
```

**Regla nueva:**
Siempre correr `npx hyperframes preview` y confirmar con el usuario antes del render final. El render es costoso; el preview es gratis.

---

## 2026-04-29 — Font size demasiado grande en video vertical

**Qué pasó:**
Los subtítulos aparecieron con texto enorme. 64px en canvas 1080px es ~5.9% del alto — demasiado prominente.

**Por qué pasó:**
Se usó un valor fijo de 64px sin calcular proporcionalmente según las dimensiones reales del video.

**Cómo detectarlo:**
Extraer frame de verificación después del primer render y mostrar al usuario antes de continuar.

**Fix exacto:**
```python
# Fórmula validada para video 1920×3414
FONT_SIZE = 15  # px — validado por el usuario para videoprueba

# Fórmula genérica para otros videos
# H = altura del canvas HyperFrames (siempre 1080 para el WebM)
FONT_SIZE = int(1080 * 0.004)  # = 4px aprox — ajustar con preview
# Valor real validado: 15px para este video
```

**Regla nueva:**
Valor validado para videoprueba (9:16, visualizado en teléfono): **44px en WebM** → ~25px real en pantalla.
Fórmula: `tamaño_deseado_px / 0.5625` donde 0.5625 = factor escala 1920→1080.
Para nuevos videos usar `int(25 / factor_escala)` como punto de partida.

---

## 2026-04-29 — Subtítulos demasiado abajo (tocando borde)

**Qué pasó:**
Los subtítulos quedaron demasiado cerca del borde inferior del frame, visualmente mal posicionados.

**Por qué pasó:**
Se usó `bottom: 100px` sin verificar cómo se ve en el video vertical real.

**Cómo detectarlo:**
Extraer frame con `ffmpeg -ss 5 -i final.mp4 -vframes 1 check.jpg` y verificar posición visual.

**Fix exacto:**
```css
/* Valor validado para videoprueba */
.sub-wrap {
  bottom: 280px;  /* validado por el usuario */
}

/* Reglas de rango:
   < 150px → toca el borde inferior → prohibido
   > 500px → queda en la mitad del frame → prohibido
   Rango válido: 150px – 500px
   Valor recomendado: 280px */
```

**Regla nueva:**
Valor validado para videoprueba: **bottom: 280px**. Rango permitido: 150–500px. Nunca menos de 150px (toca el borde), nunca más de 500px (queda en la mitad).

---

## 2026-04-29 — Recuadro negro detrás del texto sin consultar al usuario

**Qué pasó:**
Se agregó/omitió el recuadro negro semitransparente sin preguntar al usuario su preferencia de estilo.

**Por qué pasó:**
El agente tomó una decisión estética unilateral en lugar de ofrecer las dos opciones.

**Cómo detectarlo:**
Si el código tiene `background:` en `.sub-wrap` o `.word` sin que el usuario lo haya confirmado → error de proceso.

**Fix exacto — dos opciones listas para usar:**

**Opción A — Solo texto con sombra (limpio):**
```css
.sub-wrap {
  background: transparent;
}
.word {
  background: transparent;
  color: #FFFFFF;
  text-shadow: 1px 1px 4px rgba(0,0,0,0.85), 0 0 8px rgba(0,0,0,0.6);
}
```

**Opción B — Recuadro semitransparente (legible sobre fondos complejos):**
```css
.sub-wrap {
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(6px);
  padding: 10px 20px;
  border-radius: 10px;
}
.word {
  color: #FFFFFF;
  text-shadow: none;
}
```

**Regla nueva:**
Antes de generar el HTML de subtítulos, preguntar siempre: *"¿Recuadro semitransparente detrás del texto, o solo texto con sombra?"* No elegir sin confirmación del usuario.

---

## 2026-04-29 — VP9 alpha no decodifica sin -vcodec libvpx-vp9

**Qué pasó:**
El composite ffmpeg producía video negro (2MB para 65s) porque el WebM VP9 con ALPHA_MODE=1 se decodificaba como opaco (0% transparencia).

**Por qué pasó:**
ffmpeg usa por defecto el decoder nativo `vp9` que no soporta el alpha track dependiente de VP9. El decoder `libvpx-vp9` sí lo soporta.

**Cómo detectarlo:**
```bash
ffmpeg -i subtitles.webm -ss 1 -vframes 1 -pix_fmt rgba -f rawvideo pipe: 2>/dev/null \
  | python -c "
import sys; d=sys.stdin.buffer.read(); p=len(d)//4
a0=sum(1 for i in range(p) if d[i*4+3]<10)
print('Alpha working:', a0>0, f'({100*a0/p:.0f}% transparent)')
"
# Si dice 'False' → usar -vcodec libvpx-vp9
```

**Fix exacto:**
```bash
ffmpeg -y \
  -i base_video.mp4 \
  -vcodec libvpx-vp9 \
  -i subtitles.webm \
  -filter_complex "[0:v][1:v]overlay=x=0:y=0:format=auto[vout]" \
  -map "[vout]" -map "0:a" \
  -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart \
  final_video.mp4
```

**Regla nueva:**
Siempre agregar `-vcodec libvpx-vp9` ANTES del `-i subtitles.webm` al compositar WebM con alpha VP9. Verificar con el test de alpha antes de compositar.

---

## TEMPLATE PARA NUEVOS ERRORES

```markdown
## [FECHA] — [TÍTULO CORTO]

**Qué pasó:**


**Por qué pasó:**


**Cómo detectarlo:**
```bash o python

```

**Fix exacto:**
```bash o python

```

**Regla nueva:**
[Una oración imperativa]
```
