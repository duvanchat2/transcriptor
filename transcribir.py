import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import requests
import whisper

# Fix Windows console encoding for emojis
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = ' '.join(str(a) for a in args)
        print(text.encode('ascii', errors='replace').decode(), **kwargs)

DEFAULT_INPUT = "dataset_instagram-scraper_2026-04-03_18-07-32-620.json"
DEFAULT_OUTPUT = "dataset_transcrito.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe audio/video URLs from an Instagram scraper JSON dataset."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Input JSON dataset path.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output JSON path.")
    parser.add_argument("--model", default="base", help="Whisper model name.")
    parser.add_argument("--language", default="es", help="Transcription language code.")
    parser.add_argument(
        "--save-every",
        type=int,
        default=5,
        help="Persist progress after this many processed items.",
    )
    return parser.parse_args()


def load_existing_output(output_path: Path) -> tuple[list[dict], set[str]]:
    if not output_path.exists():
        return [], set()

    with output_path.open(encoding="utf-8") as f:
        output = json.load(f)
    done_ids = {item["id"] for item in output if item.get("transcription")}
    safe_print(f"Retomando: {len(done_ids)} ya transcritos")
    return output, done_ids


def save_output(output_path: Path, output: list[dict]) -> None:
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


def transcribe_dataset(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output)

    safe_print(f"Cargando modelo Whisper ({args.model})...")
    model = whisper.load_model(args.model)

    with input_path.open(encoding="utf-8") as f:
        data = json.load(f)

    output, done_ids = load_existing_output(output_path)
    total = len(data)

    for i, item in enumerate(data):
        item_id = item["id"]
        if item_id in done_ids:
            safe_print(f"[{i+1}/{total}] Ya transcrito: {item_id[:12]}...")
            continue

        audio_url = item.get("audioUrl") or item.get("videoUrl")
        if not audio_url:
            safe_print(f"[{i+1}/{total}] Sin audio: {item_id[:12]}")
            item["transcription"] = None
            output.append(item)
            continue

        tmp_path = None
        try:
            caption = item.get("caption", "")
            safe_print(f"[{i+1}/{total}] Descargando {item.get('shortCode', item_id)} | {caption[:50]}...")
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(audio_url, headers=headers, timeout=60, stream=True)
            resp.raise_for_status()

            suffix = ".mp4" if item.get("videoUrl") == audio_url else ".mp3"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                for chunk in resp.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        tmp.write(chunk)
                tmp_path = tmp.name

            safe_print("  Transcribiendo con Whisper...")
            result = model.transcribe(tmp_path, language=args.language)
            item["transcription"] = result["text"].strip()
            safe_print(f"  OK: {item['transcription'][:80]}...")

        except Exception as e:
            safe_print(f"  ERROR: {e}")
            item["transcription"] = f"ERROR: {e}"
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        output.append(item)

        if args.save_every > 0 and len(output) % args.save_every == 0:
            save_output(output_path, output)
            safe_print(f"  Progreso guardado ({len(output)} items)")

    save_output(output_path, output)

    transcribed = sum(
        1
        for item in output
        if item.get("transcription")
        and not str(item.get("transcription", "")).startswith("ERROR")
    )
    safe_print(f"\nListo! {transcribed}/{total} videos transcritos -> {output_path}")
    return 0


def main() -> int:
    return transcribe_dataset(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
