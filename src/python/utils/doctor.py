"""Environment check for RCY. Run with `just doctor`.

Reports the interpreter, uv, bundled presets, audio output and MIDI hardware.
Exits non-zero only when the headless path (slice + export) cannot work.
"""

import pathlib
import platform
import shutil
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent


def _line(label: str, value: str) -> None:
    print(f"{label:<18} {value}")


def check_python() -> bool:
    ok = sys.version_info >= (3, 11)
    _line("python", f"{platform.python_version()} ({sys.executable})")
    if not ok:
        _line("", "RCY needs Python 3.11 or newer")
    return ok


def check_uv() -> None:
    uv = shutil.which("uv")
    if uv is None:
        _line("uv", "not on PATH (https://docs.astral.sh/uv/)")
        return
    out = subprocess.run([uv, "--version"], capture_output=True, text=True, check=False)  # noqa: S603
    _line("uv", out.stdout.strip() or out.stderr.strip())


def check_presets() -> bool:
    from config_manager import config

    bundled = {}
    downloaded = {}
    for preset_id, info in config.presets.items():
        target = downloaded if info["filepath"].startswith("sample-packs/") else bundled
        target[preset_id] = (REPO_ROOT / info["filepath"]).is_file()
    bundled_ok = sum(bundled.values())
    _line("presets", f"{bundled_ok}/{len(bundled)} bundled audio files present")
    for preset_id, present in sorted(bundled.items()):
        if not present:
            _line("", f"missing: {preset_id} -> {config.presets[preset_id]['filepath']}")
    if downloaded:
        _line("rhythm-lab", f"{sum(downloaded.values())}/{len(downloaded)} audio files present "
                            "(downloaded separately, see sample-packs/README.md)")
    return bundled_ok > 0


def check_sample_packs() -> None:
    packs = REPO_ROOT / "sample-packs"
    wavs = list(packs.glob("*/audio/*.wav")) if packs.is_dir() else []
    _line("sample-packs", f"{len(wavs)} wav files under sample-packs/*/audio/")


def check_audio_output() -> None:
    try:
        import sounddevice as sd
        device = sd.query_devices(kind="output")
    except Exception as e:
        _line("audio output", f"unavailable ({e.__class__.__name__}: {e})")
        _line("", "rcy-export opens an output stream; the TUI needs one to play")
        return
    _line("audio output", f"{device['name']} ({int(device['default_samplerate'])} Hz)")


def check_midi() -> None:
    try:
        import mido
        inputs = mido.get_input_names()
        outputs = mido.get_output_names()
    except Exception as e:
        _line("midi", f"backend unavailable ({e.__class__.__name__}: {e})")
        _line("", "install the hardware extra: uv sync --extra hardware")
        return
    if not inputs and not outputs:
        _line("midi", "no MIDI ports (S2800, EP-133 and MPC tools need one)")
        return
    _line("midi inputs", ", ".join(inputs) or "none")
    _line("midi outputs", ", ".join(outputs) or "none")


def main() -> int:
    print(f"RCY doctor  ({REPO_ROOT})")
    ok = check_python()
    check_uv()
    ok = check_presets() and ok
    check_sample_packs()
    check_audio_output()
    check_midi()
    print("ok" if ok else "not ok: fix the lines above before running just smoke")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
