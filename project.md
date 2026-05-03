# project.md — Estado del pipeline
_Actualizado: 2026-04-30_

---

## 1. Video activo

| Campo | Valor |
|---|---|
| **Video fuente** | `C:/Users/duvan/OneDrive/Documentos/transcriptor/videos_editar/videoprueba.mp4` |
| **Contenido** | Claude + Blender connector — video vertical para Reels/TikTok |
| **Dimensiones fuente** | 1920 × 3414 px |
| **Duración fuente** | ~74s |

> ⚠️ Hay un `videoprueba.MP4` en la raíz del proyecto — ese es el video VIEJO (AgentMD).
> El video activo está en `videos_editar/videoprueba.mp4`.

---

## 2. Rutas del proyecto

| Contexto | Ruta |
|---|---|
| **Directorio base** | `C:/Users/duvan/OneDrive/Documentos/transcriptor/` |
| **Videos a editar** | `videos_editar/` |
| **Directorio de edición** | `edit/` (este directorio) |
| **Skill video-use** | `C:/Users/duvan/skills/video-use/` |
| **Helpers** | `C:/Users/duvan/skills/video-use/helpers/` |

---

## 3. APIs y modelos

| Campo | Valor |
|---|---|
| **Transcripción** | AssemblyAI `universal-2` (word-level timestamps) |
| **API key** | En `~/skills/video-use/.env` como `ASSEMBLYAI_API_KEY` |
| **Audio para ASR** | mono 16kHz PCM WAV (extraído con ffmpeg antes del upload) |

---

## 4. Estado actual del pipeline

### FASE 1 — Cortar silencios ✅ COMPLETA
```
EDL:  edit/edl_videoprueba.json
      6 segmentos · corta 3 tomas fallidas de "Acaba de sacar/lanzar"
      Duración total output: ~65s

Base: videos_editar/edit/base_videoprueba.mp4
      147.6 MB · 1920×3414 · 65s · sin subtítulos
```

### FASE 2 — Transcribir ⚠️ PENDIENTE REVISIÓN
```
Transcript: edit/transcripts/videoprueba.json
            Transcrito del VIDEO FUENTE (no del base)
            → Los timestamps son del fuente, se usó remap en gen_subtitles_hf.py

IMPORTANTE: El pipeline correcto según el PROMPT_AGENTE es transcribir el BASE,
no el fuente. Esto evita el remap completamente.
Considerar re-transcribir base_videoprueba.mp4 en la próxima iteración.
```

### FASE 3 — Subtítulos HyperFrames ✅ COMPLETA
```
Composición: edit/hyperframes/subtitles-comp/index.html
             63 cues · 2 palabras/cue · font-size 52px · slide-up GSAP
             Canvas: 1080×1920 (portrait, sin factor de escala)
             Option A: texto con sombra, fondo transparente

WebM:        edit/clips_hf/subtitles.webm
             1.6 MB · 1080×1920 · VP9 ALPHA_MODE=1 · 64.97s
             NOTA: requiere -vcodec libvpx-vp9 para decodificar alpha

Composite:   videos_editar/edit/final_videoprueba.mp4
             52 MB · 1080×1920 · overlay y=0 · 65s
             Comando: ffmpeg -i base -vcodec libvpx-vp9 -i subs.webm ...
```

### FASE 4 — Motion graphics ❌ NO INICIADA (siguiente paso)

---

## 5. Archivos generados (sesión actual)

```
edit/
├── project.md                              ← este archivo
├── ERRORS.md                               ← registro de errores del agente
├── edl_videoprueba.json                    ← 6 segmentos de corte
├── transcripts/videoprueba.json            ← AssemblyAI del VIDEO FUENTE
├── hyperframes/subtitles-comp/
│   ├── CLAUDE.md                           ← reglas del framework
│   ├── index.html                          ← composición HTML (93 cues)
│   └── meta.json
├── clips_hf/subtitles.webm                 ← overlay con alpha (2.7 MB)
└── clips_draft/seg_00..12_*.mp4            ← drafts de segmentos (video viejo)

videos_editar/edit/
├── base_videoprueba.mp4                    ← base limpia (147.6 MB)
└── final_videoprueba.mp4                   ← composite con subs (90.1 MB) ⚠️ errores
```

---

## 6. Errores conocidos de esta sesión

Ver `edit/ERRORS.md` para lista completa. Resumen:

1. Se transcribió el video fuente en vez del base → remap aplicado manualmente
2. Primer overlay fue MP4 (sin alpha) → rectángulo blanco → corregido a WebM
3. Caché de intermedios tapó cambios de estilo → borrado manual
4. `\f` en f-string corrompió rutas → reescrito con Path()
5. Font size 64px resultó grande visualmente → pendiente ajuste
6. Skills HyperFrames no instalados → HTML generado sin validación del framework
7. No se usó `npx hyperframes preview` antes del render

---

## 7. Notas técnicas

- **Video vertical:** 1920×3414. El overlay WebM (1920×1080) se posiciona en y=2334 (bottom del frame).
- **Subtítulos actuales:** `font-size: 64px` dentro del canvas 1080px → ~5.9% del alto → demasiado grande.
  Recomendado: `int(1080 * 0.035)` = 38px.
- **Remap de timestamps:** `gen_subtitles_hf.py` convierte source_timestamps → output_timeline.
  El pipeline ideal es transcribir el base directamente para evitar este paso.
- **Siempre ejecutar con** `PYTHONIOENCODING=utf-8` en Windows para evitar errores de encoding.
- **Rutas:** Siempre `Path()` o forward slashes. Nunca backslash en f-strings.

---

## 8. Próximos pasos (Fase 3 — corrección)

1. Identificar errores visuales específicos con el usuario (screenshot o descripción)
2. Corregir según feedback:
   - Font size: cambiar a ~38px en `gen_subtitles_hf.py` → regenerar HTML → lint → preview → render WebM
   - Timing: re-transcribir `base_videoprueba.mp4` directamente para eliminar remap
   - Posición: ajustar `BOTTOM_PX` si los subs no están bien ubicados
3. Borrar todos los intermedios antes de re-renderear
4. `npx hyperframes preview` → confirmar visualmente → render WebM → composite

---

## 9. Historial de videos procesados (batch)

| Video | Estado | Duración output |
|---|---|---|
| IMG_9655 | ✅ Completo | ~149s |
| IMG_9656 | ✅ Completo | ~74s |
| IMG_9657 | ✅ Completo (render_remaining.py) | pendiente verificar |
| IMG_9658 | ✅ Completo | pendiente verificar |
| IMG_9659 | ✅ Completo | pendiente verificar |
| IMG_9660 | ✅ Completo | pendiente verificar |
| videoprueba | ⚠️ Fase 3 con errores | 65s |
