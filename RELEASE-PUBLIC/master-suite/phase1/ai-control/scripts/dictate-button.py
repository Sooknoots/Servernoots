def get_x11_focus_and_cursor():
    win_id = None
    mouse = None
    if shutil.which("xdotool"):
        try:
            win_id = subprocess.check_output(["xdotool", "getwindowfocus"], text=True).strip()
        except Exception:
            pass
        try:
            loc = subprocess.check_output(["xdotool", "getmouselocation"], text=True).strip()
            # loc: 'x:123 y:456 screen:0 window:1234567'
            mouse = {k: int(v) for k, v in (kv.split(":") for kv in loc.split() if ":" in kv)}
        except Exception:
            pass
    return win_id, mouse

def restore_x11_focus_and_cursor(win_id, mouse, click=False):
    if shutil.which("xdotool") and win_id:
        try:
            subprocess.run(["xdotool", "windowactivate", "--sync", win_id], check=False)
        except Exception:
            pass
    if shutil.which("xdotool") and mouse:
        try:
            subprocess.run(["xdotool", "mousemove", str(mouse.get("x",0)), str(mouse.get("y",0))], check=False)
            if click:
                subprocess.run(["xdotool", "click", "1"], check=False)
        except Exception:
            pass
#!/usr/bin/env python3
import argparse
import json
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import uuid
import wave
from pathlib import Path


def parse_dotenv(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return values
    for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def resolve_endpoint(args: argparse.Namespace, env_values: dict[str, str]) -> str:
    if args.endpoint:
        return args.endpoint.strip()

    host_port = env_values.get("OPENWHISPER_HOST_PORT") or os.getenv("OPENWHISPER_HOST_PORT") or "9001"
    return f"http://127.0.0.1:{host_port}/v1/audio/transcriptions"


def post_transcription(endpoint: str, wav_path: str, timeout: int = 120) -> str:
    boundary = f"----dictate-{uuid.uuid4().hex}"
    with open(wav_path, "rb") as handle:
        audio = handle.read()

    file_head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="recording.wav"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode("utf-8")
    fields = [
        ("model", "whisper-1"),
        ("response_format", "json"),
        ("vad_filter", "false"),
    ]
    field_chunks = []
    for key, value in fields:
        field_chunks.append(
            (
                f"\r\n--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n{value}'
            ).encode("utf-8")
        )
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    payload = file_head + audio + b"".join(field_chunks) + tail

    req = urllib.request.Request(endpoint, data=payload, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Accept", "application/json")

    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    parsed = json.loads(body)
    text = str(parsed.get("text") or parsed.get("transcript") or "").strip()
    return text


def copy_to_clipboard(text: str) -> bool:
    if not text:
        return False

    if shutil.which("wl-copy"):
        proc = subprocess.run(["wl-copy"], input=text, text=True, check=False)
        if proc.returncode == 0:
            return True

    if shutil.which("xclip"):
        proc = subprocess.run(["xclip", "-selection", "clipboard"], input=text, text=True, check=False)
        if proc.returncode == 0:
            return True

    return False


def paste_clipboard(insert_mode: str) -> str:
    is_x11 = bool(os.getenv("DISPLAY")) and shutil.which("xdotool")
    is_wayland = bool(os.getenv("WAYLAND_DISPLAY")) and shutil.which("wtype")

    if insert_mode in {"auto", "x11", "clipboard"} and is_x11:
        for key_combo in (["ctrl+v"], ["ctrl+shift+v"]):
            proc = subprocess.run(["xdotool", "key", "--clearmodifiers", *key_combo], check=False)
            if proc.returncode == 0:
                return "pasted_clipboard_x11"
        if insert_mode == "x11":
            return "x11_paste_failed"

    if insert_mode in {"auto", "wayland", "clipboard"} and is_wayland:
        for key_name in ("v", "Insert"):
            proc = subprocess.run(["wtype", "-M", "ctrl", "-k", key_name, "-m", "ctrl"], check=False)
            if proc.returncode == 0:
                return "pasted_clipboard_wayland"
        proc = subprocess.run(["wtype", "-M", "ctrl", "-M", "shift", "-k", "v", "-m", "shift", "-m", "ctrl"], check=False)
        if proc.returncode == 0:
            return "pasted_clipboard_wayland"
        if insert_mode == "wayland":
            return "wayland_paste_failed"

    return "clipboard_only"


def insert_at_cursor(text: str, mode: str, type_delay_ms: int) -> str:
    if not text:
        return "empty"

    is_x11 = bool(os.getenv("DISPLAY")) and shutil.which("xdotool")
    is_wayland = bool(os.getenv("WAYLAND_DISPLAY")) and shutil.which("wtype")

    if mode in {"auto", "x11"} and is_x11:
        proc = subprocess.run(
            ["xdotool", "type", "--clearmodifiers", "--delay", str(max(0, type_delay_ms)), text],
            check=False,
        )
        if proc.returncode == 0:
            return "typed_x11"
        if mode == "x11":
            return "x11_failed"

    if mode in {"auto", "wayland"} and is_wayland:
        proc = subprocess.run(["wtype", text], check=False)
        if proc.returncode == 0:
            return "typed_wayland"
        if mode == "wayland":
            return "wayland_failed"

    if copy_to_clipboard(text):
        return paste_clipboard(mode)
    return "no_insert_backend"


def send_notification(title: str, body: str) -> None:
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", title, body], check=False)


def play_audio_cue(kind: str, enabled: bool) -> None:
    if not enabled:
        return

    if shutil.which("canberra-gtk-play"):
        event_id = "audio-input-microphone" if kind == "start" else "complete"
        subprocess.run(["canberra-gtk-play", "-i", event_id], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    if shutil.which("paplay"):
        candidates = {
            "start": [
                "/usr/share/sounds/freedesktop/stereo/audio-input-microphone.oga",
                "/usr/share/sounds/freedesktop/stereo/message.oga",
            ],
            "stop": [
                "/usr/share/sounds/freedesktop/stereo/complete.oga",
                "/usr/share/sounds/freedesktop/stereo/message.oga",
            ],
        }
        for path in candidates.get(kind, []):
            if Path(path).exists():
                subprocess.run(["paplay", path], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return


def build_record_command(arecord_device: str, wav_path: str) -> list[str]:
    if shutil.which("parec") and not arecord_device:
        return [
            "parec",
            "--format=s16le",
            "--channels=1",
            "--rate=16000",
            "--file-format=wav",
            wav_path,
        ]

    cmd = ["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1"]
    if arecord_device:
        cmd.extend(["-D", arecord_device])
    cmd.append(wav_path)
    return cmd


def stop_recording_process(pid: int) -> None:
    if pid <= 0:
        return

    try:
        os.kill(pid, 2)
    except ProcessLookupError:
        return
    except Exception:
        pass

    for _ in range(30):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        except Exception:
            break
        time.sleep(0.05)

    try:
        os.kill(pid, 15)
    except ProcessLookupError:
        return
    except Exception:
        pass

    for _ in range(30):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        except Exception:
            break
        time.sleep(0.05)

    try:
        os.kill(pid, 9)
    except Exception:
        pass


def analyze_wav(wav_path: str) -> dict[str, float | int | bool]:
    stats: dict[str, float | int | bool] = {
        "ok": False,
        "frames": 0,
        "rate": 0,
        "channels": 0,
        "duration": 0.0,
        "rms": 0.0,
        "peak": 0,
        "size_bytes": 0,
    }
    path = Path(wav_path)
    if not path.exists():
        return stats

    stats["size_bytes"] = path.stat().st_size
    try:
        with wave.open(wav_path, "rb") as wf:
            channels = int(wf.getnchannels())
            rate = int(wf.getframerate())
            frames = int(wf.getnframes())
            sampwidth = int(wf.getsampwidth())
            raw = wf.readframes(frames)

        stats["channels"] = channels
        stats["rate"] = rate
        stats["frames"] = frames
        stats["duration"] = (frames / float(rate)) if rate > 0 else 0.0

        if sampwidth == 2 and raw:
            import array

            samples = array.array("h")
            samples.frombytes(raw)
            if samples:
                peak = max(abs(v) for v in samples)
                mean_sq = sum(float(v) * float(v) for v in samples) / len(samples)
                stats["peak"] = int(peak)
                stats["rms"] = float(math.sqrt(mean_sq))

        stats["ok"] = True
        return stats
    except Exception:
        return stats


def state_file_path(custom_path: str) -> str:
    if custom_path:
        return custom_path
    runtime = os.getenv("XDG_RUNTIME_DIR", "")
    if runtime:
        return str(Path(runtime) / "dictate-toggle-state.json")
    return "/tmp/dictate-toggle-state.json"


def start_toggle_recording(
    path: str,
    arecord_device: str,
    endpoint: str,
    insert_mode: str,
    type_delay_ms: int,
    audio_cues: bool,
    min_seconds: float,
    min_rms: float,
) -> str:
    if not shutil.which("parec") and not shutil.which("arecord"):
        return "Missing recorder backend. Install: sudo apt install alsa-utils (or pulseaudio-utils)"

    if Path(path).exists():
        return "Already recording (press hotkey again to stop)"

    fd, wav_path = tempfile.mkstemp(prefix="dictate-toggle-", suffix=".wav")
    os.close(fd)

    cmd = build_record_command(arecord_device=arecord_device, wav_path=wav_path)

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
    win_id, mouse = get_x11_focus_and_cursor() if insert_mode in ("auto", "x11") else (None, None)
    state = {
        "pid": int(proc.pid),
        "wav_path": wav_path,
        "endpoint": endpoint,
        "insert_mode": insert_mode,
        "type_delay_ms": int(type_delay_ms),
        "audio_cues": bool(audio_cues),
        "min_seconds": float(min_seconds),
        "min_rms": float(min_rms),
        "started_at": time.time(),
        "x11_win_id": win_id,
        "x11_mouse": mouse,
    }
    Path(path).write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    play_audio_cue("start", enabled=audio_cues)
    send_notification("Dictate", "Recording started")
    return "Recording started"


def stop_toggle_recording(path: str) -> str:
    state_path = Path(path)
    if not state_path.exists():
        return "Not recording"

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        state_path.unlink(missing_ok=True)
        return "State file unreadable"

    pid = int(state.get("pid", 0) or 0)
    wav_path = str(state.get("wav_path") or "")
    endpoint = str(state.get("endpoint") or "")
    insert_mode = str(state.get("insert_mode") or "auto")
    type_delay_ms = int(state.get("type_delay_ms", 1) or 1)
    audio_cues = bool(state.get("audio_cues", True))
    min_seconds = float(state.get("min_seconds", 0.35) or 0.35)
    min_rms = float(state.get("min_rms", 80.0) or 80.0)
    x11_win_id = state.get("x11_win_id")
    x11_mouse = state.get("x11_mouse")

    if pid > 0:
        stop_recording_process(pid)

    state_path.unlink(missing_ok=True)

    if not wav_path or not Path(wav_path).exists():
        send_notification("Dictate", "Recording file missing")
        return "Recording file missing"

    wav_stats = analyze_wav(wav_path)
    duration = float(wav_stats.get("duration", 0.0) or 0.0)
    rms = float(wav_stats.get("rms", 0.0) or 0.0)
    stats_label = f"duration={duration:.2f}s,rms={rms:.0f},bytes={int(wav_stats.get('size_bytes', 0) or 0)}"
    if not bool(wav_stats.get("ok")):
        send_notification("Dictate", "Captured audio is invalid WAV")
        return f"Captured audio is invalid WAV ({stats_label})"
    if duration < min_seconds:
        send_notification("Dictate", "Recording too short")
        return f"Recording too short ({stats_label})"
    if rms < min_rms:
        send_notification("Dictate", "Captured silence / mic input too low")
        return f"Captured silence / mic input too low ({stats_label})"

    try:
        text = post_transcription(endpoint, wav_path)
        if not text:
            play_audio_cue("stop", enabled=audio_cues)
            send_notification("Dictate", "No speech detected")
            return f"No speech detected ({stats_label})"
        # Restore focus/cursor before insert (X11 only for now)
        if insert_mode in ("auto", "x11") and x11_win_id:
            restore_x11_focus_and_cursor(x11_win_id, x11_mouse, click=True)
        result = insert_at_cursor(text, mode=insert_mode, type_delay_ms=type_delay_ms)
        play_audio_cue("stop", enabled=audio_cues)
        if result in {"typed_x11", "typed_wayland", "pasted_clipboard_x11", "pasted_clipboard_wayland"}:
            send_notification("Dictate", "Transcript inserted")
            return "Transcript inserted"
        if result == "clipboard_only":
            send_notification("Dictate", "Copied transcript to clipboard (paste manually)")
            return "Copied transcript to clipboard (paste manually)"
        send_notification("Dictate", "Transcribed but could not insert")
        return f"Transcribed but could not insert ({result})"
    except Exception as exc:
        send_notification("Dictate", f"Transcription failed: {exc}")
        return f"Transcription failed: {exc}"
    finally:
        try:
            os.remove(wav_path)
        except FileNotFoundError:
            pass


class DictateButtonApp:
    def __init__(self, endpoint: str, arecord_device: str, insert_mode: str, type_delay_ms: int) -> None:
        import tkinter as tk

        self.endpoint = endpoint
        self.arecord_device = arecord_device
        self.insert_mode = insert_mode
        self.type_delay_ms = type_delay_ms

        self.record_proc: subprocess.Popen[str] | None = None
        self.record_path = ""

        self.root = tk.Tk()
        self.root.title("Dictate")
        self.root.geometry("420x210")
        self.root.attributes("-topmost", True)

        self.status_var = tk.StringVar(value="Ready")
        self.preview_var = tk.StringVar(value="")

        top = tk.Frame(self.root)
        top.pack(fill="x", padx=12, pady=12)

        self.record_btn = tk.Button(top, text="● Record", command=self.toggle_recording, height=2, width=14)
        self.record_btn.pack(side="left")

        self.insert_btn = tk.Button(top, text="Insert Last", command=self.insert_last_transcript, height=2, width=14)
        self.insert_btn.pack(side="left", padx=(8, 0))

        self.status_label = tk.Label(self.root, textvariable=self.status_var, anchor="w", justify="left")
        self.status_label.pack(fill="x", padx=12)

        self.preview_title = tk.Label(self.root, text="Last transcript:", anchor="w")
        self.preview_title.pack(fill="x", padx=12, pady=(10, 0))

        self.preview_entry = tk.Entry(self.root, textvariable=self.preview_var)
        self.preview_entry.pack(fill="x", padx=12, pady=(2, 0))

        endpoint_label = tk.Label(self.root, text=f"STT: {self.endpoint}", anchor="w", fg="#555")
        endpoint_label.pack(fill="x", padx=12, pady=(10, 0))

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def run(self) -> None:
        self.root.mainloop()

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def toggle_recording(self) -> None:
        if self.record_proc is None:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self) -> None:
        if not shutil.which("parec") and not shutil.which("arecord"):
            self.set_status("Missing recorder backend. Install: alsa-utils or pulseaudio-utils")
            return

        fd, path = tempfile.mkstemp(prefix="dictate-", suffix=".wav")
        os.close(fd)
        cmd = build_record_command(arecord_device=self.arecord_device, wav_path=path)

        self.record_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
        self.record_path = path
        self.record_btn.configure(text="■ Stop")
        self.set_status("Recording... press Stop when done")

    def stop_recording(self) -> None:
        proc = self.record_proc
        self.record_proc = None
        self.record_btn.configure(text="● Record")
        if proc is None:
            return

        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

        path = self.record_path
        self.record_path = ""
        self.set_status("Transcribing...")
        thread = threading.Thread(target=self.transcribe_and_insert, args=(path,), daemon=True)
        thread.start()

    def transcribe_and_insert(self, wav_path: str) -> None:
        try:
            text = post_transcription(self.endpoint, wav_path)
            if not text:
                self.root.after(0, lambda: self.set_status("No speech detected"))
                return

            self.root.after(0, lambda: self.preview_var.set(text))
            result = insert_at_cursor(text, mode=self.insert_mode, type_delay_ms=self.type_delay_ms)
            if result == "typed_x11":
                self.root.after(0, lambda: self.set_status("Inserted at cursor (X11)"))
            elif result == "typed_wayland":
                self.root.after(0, lambda: self.set_status("Inserted at cursor (Wayland)"))
            elif result == "clipboard_only":
                self.root.after(0, lambda: self.set_status("Copied to clipboard (paste manually)"))
            elif result == "x11_failed":
                self.root.after(0, lambda: self.set_status("X11 insert failed"))
            elif result == "wayland_failed":
                self.root.after(0, lambda: self.set_status("Wayland insert failed"))
            elif result == "x11_paste_failed":
                self.root.after(0, lambda: self.set_status("X11 paste failed (clipboard copied)"))
            elif result == "wayland_paste_failed":
                self.root.after(0, lambda: self.set_status("Wayland paste failed (clipboard copied)"))
            elif result in {"pasted_clipboard_x11", "pasted_clipboard_wayland"}:
                self.root.after(0, lambda: self.set_status("Pasted from clipboard at cursor"))
            else:
                self.root.after(0, lambda: self.set_status("No insert backend (install xdotool/wtype/xclip/wl-copy)"))
        except Exception as exc:
            self.root.after(0, lambda: self.set_status(f"Transcription failed: {exc}"))
        finally:
            try:
                os.remove(wav_path)
            except FileNotFoundError:
                pass

    def insert_last_transcript(self) -> None:
        text = self.preview_var.get().strip()
        if not text:
            self.set_status("No transcript available")
            return
        result = insert_at_cursor(text, mode=self.insert_mode, type_delay_ms=self.type_delay_ms)
        if result in {"typed_x11", "typed_wayland", "pasted_clipboard_x11", "pasted_clipboard_wayland"}:
            self.set_status("Inserted last transcript")
            return
        if result == "clipboard_only":
            self.set_status("Copied last transcript to clipboard")
            return
        self.set_status("Could not insert last transcript")

    def on_close(self) -> None:
        if self.record_proc is not None:
            try:
                self.record_proc.terminate()
            except Exception:
                pass
        self.root.destroy()


def main() -> int:
    parser = argparse.ArgumentParser(description="WhisperTalk-style local dictate button for OpenWhisper")
    parser.add_argument("--endpoint", default="", help="STT endpoint (default: http://127.0.0.1:<OPENWHISPER_HOST_PORT>/v1/audio/transcriptions)")
    parser.add_argument("--env-file", default=".env", help="Optional env file for OPENWHISPER_HOST_PORT lookup")
    parser.add_argument("--arecord-device", default="", help="Optional ALSA input device (arecord -L)")
    parser.add_argument("--insert-mode", choices=["auto", "x11", "wayland", "clipboard"], default="auto")
    parser.add_argument("--type-delay-ms", type=int, default=1, help="Keystroke delay for typed insertion")
    parser.add_argument("--min-seconds", type=float, default=0.35, help="Minimum captured audio duration before STT")
    parser.add_argument("--min-rms", type=float, default=80.0, help="Minimum RMS loudness before STT")
    parser.add_argument("--audio-cues", action="store_true", help="Play start/stop cues on default system speakers")
    parser.add_argument("--no-audio-cues", action="store_true", help="Disable start/stop cue playback")
    parser.add_argument("--toggle", action="store_true", help="Hotkey mode: first call starts recording, second call stops/transcribes/inserts")
    parser.add_argument("--start", action="store_true", help="Start recording immediately (for press-to-talk hotkey press event)")
    parser.add_argument("--stop", action="store_true", help="Stop recording and transcribe immediately (for press-to-talk key release event)")
    parser.add_argument("--state-file", default="", help="Toggle state file path (default: XDG runtime or /tmp)")
    args = parser.parse_args()
    audio_cues_enabled = True
    if args.no_audio_cues:
        audio_cues_enabled = False
    elif args.audio_cues:
        audio_cues_enabled = True

    env_values = parse_dotenv(args.env_file)
    endpoint = resolve_endpoint(args, env_values)
    state_path = state_file_path(args.state_file)

    if args.start:
        print(
            start_toggle_recording(
                path=state_path,
                arecord_device=args.arecord_device,
                endpoint=endpoint,
                insert_mode=args.insert_mode,
                type_delay_ms=max(0, args.type_delay_ms),
                audio_cues=audio_cues_enabled,
                min_seconds=max(0.0, args.min_seconds),
                min_rms=max(0.0, args.min_rms),
            )
        )
        return 0

    if args.stop:
        print(stop_toggle_recording(state_path))
        return 0

    if args.toggle:
        if Path(state_path).exists():
            print(stop_toggle_recording(state_path))
            return 0
        print(
            start_toggle_recording(
                path=state_path,
                arecord_device=args.arecord_device,
                endpoint=endpoint,
                insert_mode=args.insert_mode,
                type_delay_ms=max(0, args.type_delay_ms),
                audio_cues=audio_cues_enabled,
                min_seconds=max(0.0, args.min_seconds),
                min_rms=max(0.0, args.min_rms),
            )
        )
        return 0

    app = DictateButtonApp(
        endpoint=endpoint,
        arecord_device=args.arecord_device,
        insert_mode=args.insert_mode,
        type_delay_ms=max(0, args.type_delay_ms),
    )
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())