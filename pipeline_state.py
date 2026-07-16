from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EDIT_DIR = Path("edit")
PHASE_ORDER = ("cut_silence", "transcribe", "subtitles", "motion")
PHASE_OUTPUTS = {
    "cut_silence": lambda video_id: EDIT_DIR / f"base_{video_id}.mp4",
    "transcribe": lambda video_id: EDIT_DIR / "transcripts" / f"{video_id}.json",
    "subtitles": lambda video_id: EDIT_DIR / "clips_hf" / "subtitles.webm",
    "motion": lambda video_id: EDIT_DIR / "clips_hf" / "motion.webm",
}


class PipelineStateError(RuntimeError):
    """Raised when the saved pipeline contract does not match files on disk."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def state_path(video_id: str) -> Path:
    return EDIT_DIR / f"state_{video_id}.json"


def default_source_path(video_id: str) -> Path:
    return Path("videos_editar") / f"{video_id}.mp4"


def hash_file(path: str | Path) -> str:
    file_path = Path(path)
    digest = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _new_phase(status: str = "pending") -> dict[str, Any]:
    return {
        "status": status,
        "input_hash": None,
        "output_path": None,
        "output_hash": None,
    }


def _empty_state(video_id: str) -> dict[str, Any]:
    source_path = default_source_path(video_id)
    source_hash = hash_file(source_path) if source_path.exists() else None
    return {
        "video_id": video_id,
        "source_path": source_path.as_posix(),
        "source_hash": source_hash,
        "phases": {
            "cut_silence": _new_phase(),
            "transcribe": {
                **_new_phase(),
                "transcribed_from": None,
            },
            "subtitles": _new_phase(),
            "motion": _new_phase(),
        },
        "updated_at": utc_now(),
    }


def _normalize_state(video_id: str, state: dict[str, Any]) -> dict[str, Any]:
    normalized = _empty_state(video_id)
    normalized.update(state)
    normalized["video_id"] = video_id

    phases = normalized.setdefault("phases", {})
    for phase in PHASE_ORDER:
        defaults = normalized["phases"].get(phase) or _new_phase()
        current = phases.get(phase, {})
        defaults.update(current)
        phases[phase] = defaults

    phases["transcribe"].setdefault("transcribed_from", None)
    return normalized


def load_state(video_id: str) -> dict[str, Any]:
    path = state_path(video_id)
    if not path.exists():
        state = _empty_state(video_id)
        save_state(video_id, state)
        return state

    with path.open(encoding="utf-8") as f:
        return _normalize_state(video_id, json.load(f))


def save_state(video_id: str, state: dict[str, Any]) -> None:
    EDIT_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now()
    path = state_path(video_id)
    with path.open("w", encoding="utf-8") as f:
        json.dump(_normalize_state(video_id, state), f, ensure_ascii=False, indent=2)
        f.write("\n")


def _phase_index(phase: str) -> int:
    if phase not in PHASE_ORDER:
        raise PipelineStateError(f"Fase desconocida: {phase}")
    return PHASE_ORDER.index(phase)


def _clear_phase(phase_state: dict[str, Any]) -> None:
    phase_state["status"] = "pending"
    phase_state["input_hash"] = None
    phase_state["output_path"] = None
    phase_state["output_hash"] = None
    if "transcribed_from" in phase_state:
        phase_state["transcribed_from"] = None


def _delete_output(path_value: str | None) -> None:
    if not path_value:
        return
    path = Path(path_value)
    if path.exists() and path.is_file():
        path.unlink()


def invalidate_from_phase(video_id: str, phase: str, delete_files: bool = True) -> dict[str, Any]:
    state = load_state(video_id)
    start = _phase_index(phase)
    for phase_name in PHASE_ORDER[start:]:
        phase_state = state["phases"][phase_name]
        if delete_files:
            _delete_output(phase_state.get("output_path"))
        _clear_phase(phase_state)
    save_state(video_id, state)
    return state


def verify_phase_input(video_id: str, phase: str, expected_input_path: str | Path) -> bool:
    state = load_state(video_id)
    expected_path = Path(expected_input_path)
    if not expected_path.exists():
        raise PipelineStateError(f"No existe el input esperado para {phase}: {expected_path}")

    current_hash = hash_file(expected_path)
    phase_state = state["phases"][phase]
    previous_hash = phase_state.get("input_hash")

    if previous_hash is None:
        phase_state["input_hash"] = current_hash
        save_state(video_id, state)
        return True

    if previous_hash != current_hash:
        raise PipelineStateError(
            f"Input de {phase} cambió desde la última corrida. "
            f"Esperado {previous_hash}, actual {current_hash}. Abortando."
        )

    return True


def assert_transcribe_uses_current_base(video_id: str, base_path: str | Path) -> None:
    state = load_state(video_id)
    base = Path(base_path)
    if not base.exists():
        raise PipelineStateError(f"No existe el base para transcribir: {base}")

    base_hash = hash_file(base)
    recorded_hash = state["phases"]["cut_silence"].get("output_hash")
    if recorded_hash != base_hash:
        raise PipelineStateError(
            "El base actual no coincide con el hash registrado. "
            "¿Se re-cortó el video sin actualizar el estado?"
        )


def mark_phase_done(
    video_id: str,
    phase: str,
    output_path: str | Path,
    *,
    input_path: str | Path | None = None,
    transcribed_from: str | None = None,
) -> dict[str, Any]:
    state = load_state(video_id)
    out = Path(output_path)
    if not out.exists():
        raise PipelineStateError(f"No existe el output de {phase}: {out}")

    phase_state = state["phases"][phase]
    if input_path is not None:
        phase_state["input_hash"] = hash_file(input_path)
    phase_state["status"] = "done"
    phase_state["output_path"] = out.as_posix()
    phase_state["output_hash"] = hash_file(out)

    if phase == "cut_silence":
        source = Path(state["source_path"])
        state["source_hash"] = hash_file(source) if source.exists() else state.get("source_hash")

    if phase == "transcribe":
        if transcribed_from not in {"base", "source"}:
            raise PipelineStateError("transcribed_from debe ser 'base' o 'source'")
        phase_state["transcribed_from"] = transcribed_from

    save_state(video_id, state)
    return state


def assert_subtitles_can_run(video_id: str) -> None:
    state = load_state(video_id)
    transcribe = state["phases"]["transcribe"]
    if transcribe.get("status") != "done":
        raise PipelineStateError("No se puede correr subtitles: transcribe no está done.")

    source = transcribe.get("transcribed_from")
    if source == "base":
        return

    if source != "source":
        raise PipelineStateError("transcribed_from no está definido. Debe ser 'base' o 'source'.")

    remap_path = EDIT_DIR / f"remap_{video_id}.json"
    if not remap_path.exists():
        raise PipelineStateError(
            "Transcript viene del source. Subtitles requiere remap explícito en "
            f"{remap_path.as_posix()} antes de continuar."
        )

    mappings = json.loads(remap_path.read_text(encoding="utf-8"))
    if not isinstance(mappings, list) or len(mappings) < 5:
        raise PipelineStateError("El remap debe contener al menos 5 palabras verificables.")

    print("Primeras 5 palabras remapeadas:")
    for item in mappings[:5]:
        text = item.get("text", "")
        source_time = item.get("source_time", item.get("source_start_s"))
        output_time = item.get("output_time", item.get("start_s"))
        print(f"{text:20s} source_time={source_time} -> output_time={output_time}")


def pretty_state(video_id: str) -> str:
    return json.dumps(load_state(video_id), ensure_ascii=False, indent=2)
