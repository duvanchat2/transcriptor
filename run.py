from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from pipeline_state import (
    EDIT_DIR,
    PHASE_OUTPUTS,
    PipelineStateError,
    assert_subtitles_can_run,
    assert_transcribe_uses_current_base,
    hash_file,
    invalidate_from_phase,
    load_state,
    mark_phase_done,
    pretty_state,
    save_state,
    verify_phase_input,
)


def phase_output(video_id: str, phase: str) -> Path:
    return PHASE_OUTPUTS[phase](video_id)


def write_simulated_output(path: Path, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"simulated {label}\n", encoding="utf-8")


def cmd_status(args: argparse.Namespace) -> int:
    print(pretty_state(args.video))
    return 0


def cmd_cut(args: argparse.Namespace) -> int:
    state = invalidate_from_phase(args.video, "cut_silence")
    source_path = Path(state["source_path"])
    if not source_path.exists() and not args.simulate:
        raise PipelineStateError(f"No existe el video fuente: {source_path}")

    if args.simulate:
        source_path.parent.mkdir(parents=True, exist_ok=True)
        if not source_path.exists():
            write_simulated_output(source_path, "source video")
        state["source_hash"] = hash_file(source_path)
        save_state(args.video, state)

        output = phase_output(args.video, "cut_silence")
        write_simulated_output(output, "cut_silence output")
        mark_phase_done(args.video, "cut_silence", output, input_path=source_path)
        print(f"Simulado cut_silence -> {output.as_posix()}")
        return 0

    print("Guard listo. Ejecuta helpers/silence_cut.py y helpers/render.py para generar el base.")
    return 0


def cmd_transcribe(args: argparse.Namespace) -> int:
    base = phase_output(args.video, "cut_silence")
    if args.from_source:
        input_path = Path(load_state(args.video)["source_path"])
        transcribed_from = "source"
    else:
        input_path = base
        transcribed_from = "base"
        assert_transcribe_uses_current_base(args.video, base)

    verify_phase_input(args.video, "transcribe", input_path)
    invalidate_from_phase(args.video, "transcribe")

    if args.simulate:
        output = phase_output(args.video, "transcribe")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "words": [
                        {"text": "hola", "start": 0.1, "end": 0.3},
                        {"text": "duvan", "start": 0.4, "end": 0.7},
                    ]
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        mark_phase_done(
            args.video,
            "transcribe",
            output,
            input_path=input_path,
            transcribed_from=transcribed_from,
        )
        print(f"Simulado transcribe ({transcribed_from}) -> {output.as_posix()}")
        return 0

    print("Guard listo. Transcribe el base y luego llama mark_phase_done desde la integración real.")
    return 0


def cmd_subtitles(args: argparse.Namespace) -> int:
    assert_subtitles_can_run(args.video)
    transcript = phase_output(args.video, "transcribe")
    verify_phase_input(args.video, "subtitles", transcript)
    invalidate_from_phase(args.video, "subtitles")

    if args.simulate:
        output = phase_output(args.video, "subtitles")
        write_simulated_output(output, "subtitles webm")
        mark_phase_done(args.video, "subtitles", output, input_path=transcript)
        print(f"Simulado subtitles -> {output.as_posix()}")
        return 0

    print("Guard listo. Genera HyperFrames, lint, preview y render WebM con alpha.")
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    print("Preview debe abrirse desde edit/hyperframes/subtitles-comp con npx hyperframes preview.")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    print("Render debe producir WebM con alpha. Luego usa composite para verificar pix_fmt.")
    return 0


def pix_fmt(path: Path) -> str:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=pix_fmt",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise PipelineStateError(result.stderr.strip() or "ffprobe falló")
    return result.stdout.strip()


def cmd_composite(args: argparse.Namespace) -> int:
    overlay = phase_output(args.video, "subtitles")
    if not overlay.exists():
        raise PipelineStateError(f"No existe overlay para compositar: {overlay}")

    fmt = pix_fmt(overlay)
    if fmt != "yuva420p":
        raise PipelineStateError(
            f"Overlay sin alpha correcto: pix_fmt={fmt}. Debe ser yuva420p antes de compositar."
        )

    print(f"OK alpha: {overlay.as_posix()} pix_fmt={fmt}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Video pipeline state runner.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_video(command: str, handler, *, simulate: bool = False) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(command)
        sub.add_argument("video", help="Video id, for example: videoprueba")
        if simulate:
            sub.add_argument("--simulate", action="store_true", help="Create fake outputs for state testing.")
        sub.set_defaults(func=handler)
        return sub

    add_video("status", cmd_status)
    add_video("cut", cmd_cut, simulate=True)
    transcribe = add_video("transcribe", cmd_transcribe, simulate=True)
    transcribe.add_argument("--from-source", action="store_true", help="Mark transcript as source-based.")
    add_video("subtitles", cmd_subtitles, simulate=True)
    add_video("preview", cmd_preview)
    add_video("render", cmd_render)
    add_video("composite", cmd_composite)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        EDIT_DIR.mkdir(parents=True, exist_ok=True)
        return args.func(args)
    except PipelineStateError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
