import json
import os
import sys
import requests
import whisper
import tempfile

# Fix Windows console encoding for emojis
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = ' '.join(str(a) for a in args)
        print(text.encode('ascii', errors='replace').decode(), **kwargs)

JSON_PATH = "dataset_instagram-scraper_2026-04-03_18-07-32-620.json"
OUTPUT_PATH = "dataset_transcrito.json"

print("Cargando modelo Whisper (base)...")
model = whisper.load_model("base")

with open(JSON_PATH, encoding="utf-8") as f:
    data = json.load(f)

# Si existe progreso previo, cargarlo
if os.path.exists(OUTPUT_PATH):
    with open(OUTPUT_PATH, encoding="utf-8") as f:
        output = json.load(f)
    done_ids = {item["id"] for item in output if item.get("transcription")}
    print(f"Retomando: {len(done_ids)} ya transcritos")
else:
    output = []
    done_ids = set()

total = len(data)
for i, item in enumerate(data):
    if item["id"] in done_ids:
        safe_print(f"[{i+1}/{total}] Ya transcrito: {item['id'][:12]}...")
        continue

    audio_url = item.get("audioUrl") or item.get("videoUrl")
    if not audio_url:
        safe_print(f"[{i+1}/{total}] Sin audio: {item['id'][:12]}")
        item["transcription"] = None
        output.append(item)
        continue

    tmp_path = None
    try:
        safe_print(f"[{i+1}/{total}] Descargando {item['shortCode']} | {item.get('caption','')[:50]}...")
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(audio_url, headers=headers, timeout=60, stream=True)
        resp.raise_for_status()

        # Guardar en archivo temporal
        suffix = ".mp4" if item.get("videoUrl") == audio_url else ".mp3"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in resp.iter_content(chunk_size=1024 * 64):
                tmp.write(chunk)
            tmp_path = tmp.name

        safe_print(f"  Transcribiendo con Whisper...")
        result = model.transcribe(tmp_path, language="es")
        item["transcription"] = result["text"].strip()
        safe_print(f"  OK: {item['transcription'][:80]}...")

    except Exception as e:
        safe_print(f"  ERROR: {e}")
        item["transcription"] = f"ERROR: {e}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    output.append(item)

    # Guardar progreso cada 5 items
    if len(output) % 5 == 0:
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        safe_print(f"  Progreso guardado ({len(output)} items)")

# Guardar resultado final
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

transcribed = sum(1 for item in output if item.get("transcription") and not str(item.get("transcription","")).startswith("ERROR"))
print(f"\nListo! {transcribed}/{total} videos transcritos -> {OUTPUT_PATH}")
